"""Verify local code with the real SDK and mocked HTTP; never call ElevenLabs."""

import copy
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.types.get_test_suite_invocation_response_model import GetTestSuiteInvocationResponseModel

import evaluate


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.scenario = evaluate.read_json(evaluate.BASE / "scenarios" / "01-english-course-info.json")
        self.catalog = evaluate.read_json(evaluate.BASE / "fixtures" / "catalog.json")
        self.payload = evaluate.prepare(self.scenario, self.catalog, "tool_test")
        self.inputs = {"scenario": self.scenario, "catalog": self.catalog, "test_definition": self.payload}
        self.outcome = {
            "id": "suite_local", "agent_id": "agent_local", "branch_id": "branch_local",
            "version_id": "version_local", "ran_against_draft": False,
            "test_runs": [{
                "test_run_id": "run_local", "test_invocation_id": "suite_local",
                "agent_id": "agent_local", "test_id": "test_local", "status": "passed",
                "condition_result": {"result": "success", "rationale": {"summary": "Correct data."}},
                "agent_responses": [{
                    "role": "agent", "time_in_call_secs": 1,
                    "message": "BRL 220, Tuesdays and Thursdays, 7 pm to 8 pm.",
                    "tool_calls": [{"tool_name": "list_courses", "request_id": "req_local",
                                    "params_as_json": "{}", "tool_has_been_called": True}],
                    "tool_results": [{"tool_name": "list_courses", "is_error": False,
                                      "request_id": "req_local", "tool_has_been_called": True,
                                      "result_value": json.dumps(self.catalog)}],
                }],
            }],
        }

    def client(self, handler):
        return ElevenLabs(api_key="local-test-key-only", httpx_client=httpx.Client(
            transport=httpx.MockTransport(handler)))

    def test_sdk_serializes_mock_runs_and_queries_without_network(self):
        requests = []
        def handler(req):
            requests.append((req.method, req.url.path))
            if req.url.path.endswith("/create"):
                body = json.loads(req.content)
                self.assertEqual(body["type"], "simulation")
                self.assertEqual(body["tool_mock_config"]["fallback_strategy"], "raise_error")
                mock = body["tool_mock_overrides"]["tool_test"][0]
                self.assertEqual(json.loads(mock["mock_result"]), self.catalog)
                return httpx.Response(200, json={"id": "test_local"})
            if req.method == "POST":
                body = json.loads(req.content)
                self.assertEqual(body["repeat_count"], 1)
                self.assertEqual(body["tests"], [{"test_id": "test_local"}])
                self.assertEqual(body["branch_id"], "branch_local")
                pending = copy.deepcopy(self.outcome)
                pending["test_runs"][0]["status"] = "pending"
                return httpx.Response(200, json=pending)
            return httpx.Response(200, json=self.outcome)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp, redirect_stdout(StringIO()):
            state = Path(tmp) / "state.json"
            client = self.client(handler)
            started = evaluate.start(client, "agent_local", "branch_local", self.payload, state, self.inputs)
            result = evaluate.wait_for_result(client, started, seconds=1, interval=0)
            summary, folder = evaluate.record(Path(tmp), result, self.scenario, self.catalog, self.payload)
            self.assertEqual(summary["outcome"], "PASSED")
            self.assertTrue((folder / "conversation.txt").exists())
            self.assertIn("version_local", (folder / "summary.csv").read_text(encoding="utf-8-sig"))
            self.assertNotIn("local-test-key-only", (folder / "full-result.json").read_text())
            self.assertEqual(sum(m == "POST" for m, _ in requests), 2)
            self.assertEqual(evaluate.read_json(state)["latest_run"], "suite_local")

    def test_platform_pass_without_evidence_requires_review(self):
        self.outcome["test_runs"][0]["agent_responses"] = []
        summary = evaluate.summarize(self.outcome, self.scenario, self.catalog)
        self.assertEqual(summary["outcome"], "REVIEW_EVIDENCE")

    def test_wrong_mock_or_tool_error_cannot_pass(self):
        result = self.outcome["test_runs"][0]["agent_responses"][0]["tool_results"][0]
        result["result_value"] = '{"status": "ok", "total": 0, "courses": []}'
        self.assertEqual(evaluate.summarize(self.outcome, self.scenario, self.catalog)["outcome"], "REVIEW_EVIDENCE")
        result["result_value"] = json.dumps(self.catalog)
        result["is_error"] = True
        self.assertFalse(evaluate.summarize(self.outcome, self.scenario, self.catalog)["mock_confirmed"])

    def test_pending_or_technical_failure_cannot_pass(self):
        for status, grade in [("pending", "success"), ("failed", "unknown")]:
            self.outcome["test_runs"][0]["status"] = status
            self.outcome["test_runs"][0]["condition_result"]["result"] = grade
            self.assertEqual(evaluate.summarize(self.outcome, self.scenario, self.catalog)["outcome"], "INCONCLUSIVE")
        self.outcome["test_runs"][0]["status"] = "pending"
        response = GetTestSuiteInvocationResponseModel(**self.outcome)
        client = self.client(lambda r: self.fail("A local timeout must not query the network"))
        self.assertEqual(evaluate.wait_for_result(client, response, seconds=0)["test_runs"][0]["status"], "pending")

    def test_preview_does_not_create_client(self):
        with patch.object(evaluate, "ElevenLabs", side_effect=AssertionError("Must not create a client")), redirect_stdout(StringIO()):
            self.assertEqual(evaluate.main(["--preview"]), 0)

    def test_rejected_post_allows_key_correction_without_blocking(self):
        self.check_post_failure(401, False)

    def test_uncertain_post_is_not_retried_and_keeps_block(self):
        self.check_post_failure(500, True)

    def check_post_failure(self, status, waiting):
        count = 0
        def handler(req):
            nonlocal count
            count += 1
            return httpx.Response(status, json={"detail": "Local test error"})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp, redirect_stdout(StringIO()):
            state = Path(tmp) / "state.json"
            signature = __import__("hashlib").sha256(json.dumps(self.payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            evaluate.save_json(state, {"registrations": {signature: "test_local"}})
            with self.assertRaises(ApiError):
                evaluate.start(self.client(handler), "agent_local", "branch_local", self.payload, state, self.inputs)
            self.assertEqual(count, 1)
            self.assertEqual(evaluate.read_json(state)["waiting"], waiting)
            if waiting:
                with self.assertRaisesRegex(ValueError, "pending"):
                    evaluate.start(self.client(handler), "agent_local", "branch_local", self.payload, state, self.inputs)
                self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
