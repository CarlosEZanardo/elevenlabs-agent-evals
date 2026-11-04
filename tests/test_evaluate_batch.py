"""Local batch tests: real SDK, mocked HTTP and temporary files."""

import copy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError

import evaluate
import evaluate_batch as batch


class BatchTests(unittest.TestCase):
    def copy_inputs(self, destination):
        shutil.copytree(batch.BASE / "scenarios", destination / "scenarios")
        shutil.copytree(batch.BASE / "fixtures", destination / "fixtures")

    def client(self, handler):
        return ElevenLabs(api_key="local-test-key", httpx_client=httpx.Client(
            transport=httpx.MockTransport(handler)))

    def test_default_twenty_case_suite_preserves_first_payload(self):
        suite, inputs = batch.load_inputs(batch.BASE, "tool_local")
        self.assertEqual(len(inputs), 20)
        self.assertEqual(sum(e["case"]["purpose"] == "validation" for e in inputs), 4)
        scenario = evaluate.read_json(batch.BASE / "scenarios" / "01-english-course-info.json")
        expected = evaluate.prepare(scenario, inputs[0]["response"], "tool_local")
        self.assertEqual(inputs[0]["payload"], expected)
        self.assertEqual(batch.signature(expected), inputs[0]["signature"])
        _, selection = batch.load_inputs(batch.BASE, "tool_local", "01,11,17")
        self.assertEqual([e["case"]["id"][:2] for e in selection], ["01", "11", "17"])

    def test_preview_without_client_or_key(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copy_inputs(base)
            with patch.object(batch, "BASE", base), patch.object(batch, "load_dotenv"), \
                    patch.dict("os.environ", {}, clear=True), \
                    patch.object(batch, "ElevenLabs", side_effect=AssertionError("Must not create a client")), \
                    redirect_stdout(StringIO()):
                self.assertEqual(batch.main(["--preview"]), 0)
            plan = evaluate.read_json(base / "batch-plan.json")
            self.assertEqual(plan["count"], 20)
            self.assertEqual(plan["repeat_count"], 1)
            self.assertFalse((base / "batches").exists())

    def test_minimal_suite_preserves_definitions_and_custom_suite_has_own_limit(self):
        full_suite, _ = batch.load_inputs(batch.BASE, "tool_local")
        minimal, inputs = batch.load_inputs(
            batch.BASE, "tool_local", suite_path="scenarios/minimal-suite.json")
        self.assertEqual(minimal["version"], "1.1-minimal")
        self.assertEqual([e["case"]["id"][:2] for e in inputs], ["01", "11", "17"])
        self.assertEqual(minimal["cases"], [c for c in full_suite["cases"] if c["id"][:2] in {"01", "11", "17"}])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copy_inputs(base)
            file = base / "scenarios" / "pair.json"
            evaluate.save_json(file, {"version": "custom", "cases": copy.deepcopy(minimal["cases"][:2])})
            suite, pair = batch.load_inputs(base, "tool_local", limit=2, suite_path=file)
            self.assertEqual(suite["version"], "custom")
            self.assertEqual(len(pair), 2)
            _, selection = batch.load_inputs(base, "tool_local", "11", suite_path="scenarios/pair.json")
            self.assertEqual(len(selection), 1)
            self.assertTrue(selection[0]["case"]["id"].startswith("11-"))
            with self.assertRaisesRegex(ValueError, "between 1 and 2 for this suite"):
                batch.load_inputs(base, "tool_local", limit=3, suite_path=file)
            with self.assertRaises(ValueError) as error:
                batch.load_inputs(base, "tool_local", "17", suite_path=file)
            self.assertIn("Available IDs: 01-english-course-info, 11-office-enrollment", str(error.exception))
            self.assertIn("Available numbers: 01, 11", str(error.exception))

    def test_custom_suite_blocks_path_escape_extension_and_outside_link(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copy_inputs(base)
            for path in ("../outside.json", "scenarios/../../outside.json", ".env", "scenarios/.env"):
                with self.subTest(path=path), patch.object(batch, "read_json") as read:
                    with self.assertRaisesRegex(ValueError, ".json file inside scenarios"):
                        batch.load_inputs(base, "tool_local", suite_path=path)
                    read.assert_not_called()
            # Simulate link resolution without requiring Windows symlink privileges.
            link = base / "scenarios" / "shortcut.json"
            outside = base / "outside.json"
            resolve = Path.resolve
            def resolve_link(path, *args, **kwargs):
                return outside if path == link else resolve(path, *args, **kwargs)
            with patch.object(Path, "resolve", autospec=True, side_effect=resolve_link), \
                    patch.object(batch, "read_json") as read:
                with self.assertRaisesRegex(ValueError, "inside scenarios"):
                    batch.load_inputs(base, "tool_local", suite_path="scenarios/shortcut.json")
                read.assert_not_called()

    def test_suite_rejects_empty_cases_duplicate_ids_duplicate_names_and_zero(self):
        original = evaluate.read_json(batch.BASE / "scenarios" / "minimal-suite.json")
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copy_inputs(base)
            for change, message in (("empty", "nonempty list"), ("id", "distinct ID"),
                                       ("name", "distinct name"), ("zero", "01 to 99")):
                suite = copy.deepcopy(original)
                if change == "empty":
                    suite["cases"] = []
                elif change == "zero":
                    suite["cases"][0]["id"] = "00-invalid"
                else:
                    suite["cases"][1][change] = suite["cases"][0][change]
                evaluate.save_json(base / "scenarios" / "custom.json", suite)
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                    batch.load_inputs(base, "tool_local", suite_path="scenarios/custom.json")

    def test_custom_suite_preview_reads_local_env_without_client(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copy_inputs(base)
            (base / ".env").write_text(
                "ELEVENLABS_API_KEY=local-test-key\nELEVENLABS_AGENT_ID=agent_local\n"
                "ELEVENLABS_BRANCH_ID=branch_local\nELEVENLABS_TOOL_ID=tool_local\n", encoding="utf-8")
            with patch.object(batch, "BASE", base), patch.dict("os.environ", {}, clear=True), \
                    patch.object(batch, "ElevenLabs", side_effect=AssertionError("Must not create a client")), \
                    redirect_stdout(StringIO()):
                self.assertEqual(batch.main(["--preview", "--suite", "scenarios/minimal-suite.json"]), 0)
            plan = evaluate.read_json(base / "batch-plan.json")
            self.assertEqual(plan["count"], 3)
            self.assertEqual(plan["agent_id"], "agent_local")
            self.assertEqual(plan["suite_version"], "1.1-minimal")
            self.assertNotIn("local-test-key", (base / "batch-plan.json").read_text(encoding="utf-8"))
            self.assertFalse((base / "batches").exists())

    def test_query_rejects_explicit_suite_before_creating_client(self):
        output = StringIO()
        with patch.object(batch, "load_dotenv"), \
                patch.object(batch, "ElevenLabs", side_effect=AssertionError("Must not create a client")), \
                patch.object(batch, "load_inputs", side_effect=AssertionError("Use the snapshot")), \
                redirect_stdout(output):
            self.assertEqual(batch.main(["--query", "--suite", "scenarios/minimal-suite.json"]), 2)
        self.assertIn("saved snapshot", output.getvalue())

    def test_generic_mock_object_is_serialized_by_sdk_and_verified_in_report(self):
        _, inputs = batch.load_inputs(batch.BASE, "tool_local", "01")
        entry = copy.deepcopy(inputs[0])
        response = {"status": "confirmed", "booking": {"reference": "LOCAL-001", "services": ["wheel_alignment"]}}
        entry["response"] = response
        entry["case"]["tool"] = "lookup_booking"
        entry["payload"] = batch.build_test(entry["case"], response, "tool_local")
        entry["signature"] = batch.signature(entry["payload"])
        registrations = []
        def handler(req):
            registrations.append(json.loads(req.content))
            return httpx.Response(200, json={"id": "test_local"})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            batch.register_tests(self.client(handler), [entry], {"registrations": {}}, base / "state.json")
            mock = registrations[0]["tool_mock_overrides"]["tool_local"][0]
            self.assertEqual(json.loads(mock["mock_result"]), response)
            data = {"id": "suite_local", "test_runs": [{
                "test_id": "test_local", "test_run_id": "run_local", "status": "passed",
                "condition_result": {"result": "success"}, "credits_used": 0,
                "agent_responses": [{"role": "agent", "message": "Booking found.",
                    "tool_calls": [{"tool_name": "lookup_booking", "request_id": "req_local"}],
                    "tool_results": [{"tool_name": "lookup_booking", "request_id": "req_local",
                        "is_error": False, "result_value": json.dumps(response)}]}],
            }]}
            summary = batch.generate_reports(base / "report", data, [entry])
            self.assertEqual(summary["cases"][0]["outcome"], "PASSED")
            self.assertTrue(summary["cases"][0]["mock_confirmed"])

    def test_generic_mock_needs_no_status_and_catalog_keeps_validation(self):
        _, inputs = batch.load_inputs(batch.BASE, "tool_local", "01")
        case = inputs[0]["case"]
        for response in ({"customer": {"name": "Test person"}}, {"status": "pending"},
                        {"status": "ok", "total": 9, "items": []}):
            with self.subTest(response=response):
                payload = batch.build_test(case, response, "tool_local")
                self.assertEqual(json.loads(payload["tool_mock_overrides"]["tool_local"][0]["mock_result"]), response)
        for response in ([], None, "text", 42):
            with self.subTest(response=response), self.assertRaisesRegex(ValueError, "JSON object"):
                batch.build_test(case, response, "tool_local")
        with self.assertRaisesRegex(ValueError, "total does not match"):
            batch.build_test(case, {"status": "ok", "total": 2, "courses": []}, "tool_local")
        with self.assertRaisesRegex(ValueError, "courses must be a list"):
            batch.build_test(case, {"status": "ok", "total": 0, "courses": None}, "tool_local")

    def test_selection_accepts_unpadded_numbers_and_reports_unknown_values(self):
        _, inputs = batch.load_inputs(batch.BASE, "tool_local", "1, 11,17")
        self.assertEqual([e["case"]["id"][:2] for e in inputs], ["01", "11", "17"])
        _, inputs = batch.load_inputs(batch.BASE, "tool_local", "01-english-course-info,11,17")
        self.assertEqual([e["case"]["id"][:2] for e in inputs], ["01", "11", "17"])
        with self.assertRaisesRegex(ValueError, "Scenarios not found: '99'"):
            batch.load_inputs(batch.BASE, "tool_local", "01,11,99")

    def test_empty_selection_does_not_run_full_batch(self):
        for selection in ("", " ", ",,"):
            with self.subTest(selection=selection), self.assertRaisesRegex(ValueError, "Provide case numbers"):
                batch.load_inputs(batch.BASE, "tool_local", selection)

    def test_distinct_mocks_and_selection_validation(self):
        _, inputs = batch.load_inputs(batch.BASE, "tool_local", "16,17,18")
        mocks = [e["payload"]["tool_mock_overrides"]["tool_local"][0] for e in inputs]
        self.assertEqual([m["is_error"] for m in mocks], [False, False, True])
        self.assertEqual([json.loads(m["mock_result"])["status"] for m in mocks], ["ok", "error", "error"])
        with self.assertRaises(ValueError):
            batch.load_inputs(batch.BASE, "tool_local", "99")
        with self.assertRaises(ValueError):
            batch.load_inputs(batch.BASE, "tool_local", limit=0)

    def test_mock_path_cannot_escape_fixtures(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copy_inputs(base)
            file = base / "scenarios" / "suite-20.json"
            suite = evaluate.read_json(file)
            suite["cases"][0]["mock"]["file"] = "../.env"
            evaluate.save_json(file, suite)
            with self.assertRaisesRegex(ValueError, "inside fixtures"):
                batch.load_inputs(base, "tool_local")

    def test_sdk_batch_snapshot_reuse_and_query_without_new_run(self):
        _, originals = batch.load_inputs(batch.BASE, "tool_local", "01,11")
        inputs = copy.deepcopy(originals)
        suite = {"version": "test"}
        calls, registrations, runs_completed = [], {}, []
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp, redirect_stdout(StringIO()):
            base = Path(tmp)
            def handler(req):
                calls.append((req.method, req.url.path))
                if req.url.path.endswith("/create"):
                    body = json.loads(req.content)
                    test_id = "test_" + str(len(registrations) + 1)
                    registrations[test_id] = body
                    return httpx.Response(200, json={"id": test_id})
                if req.method == "POST":
                    body = json.loads(req.content)
                    self.assertEqual(body["repeat_count"], 1)
                    self.assertEqual(len(body["tests"]), 2)
                    state = evaluate.read_json(base / ".batch-state.json")
                    folder = batch.saved_folder(base, state["pending"]["folder"])
                    snapshot = evaluate.read_json(folder / "inputs.json")
                    self.assertTrue(all(e.get("test_id") for e in snapshot))
                    self.assertNotIn("local-test-key", (folder / "inputs.json").read_text())
                    suite_id = f"suite_local_{len(runs_completed) + 1}"
                    runs = []
                    for i, e in enumerate(reversed(snapshot)):
                        tool_calls, tool_results = [], []
                        if e["case"]["tool_expectation"] == "required":
                            tool_calls = [{"tool_name": e["case"]["tool"], "request_id": "req_local",
                                              "params_as_json": "{}", "tool_has_been_called": True}]
                            tool_results = [{"tool_name": e["case"]["tool"], "request_id": "req_local",
                                             "tool_has_been_called": True, "is_error": e["case"]["mock"]["is_error"],
                                             "result_value": json.dumps(e["response"])}]
                        runs.append({"test_run_id": f"run_{i}", "test_invocation_id": suite_id,
                                     "agent_id": "agent_local", "branch_id": "branch_local", "version_id": "v_local",
                                     "ran_against_draft": False, "test_id": e["test_id"], "status": "passed",
                                     "condition_result": {"result": "success", "rationale": {"summary": "Correct in the local test"}},
                                     "credits_used": 10, "agent_responses": [{"role": "agent", "time_in_call_secs": 0,
                                         "message": "Prepared response for testing the code.",
                                         "tool_calls": tool_calls, "tool_results": tool_results}]})
                    complete = {"id": suite_id, "agent_id": "agent_local", "branch_id": "branch_local",
                                "version_id": "v_local", "ran_against_draft": False, "test_runs": runs}
                    runs_completed.append(complete)
                    pending = copy.deepcopy(complete)
                    for run in pending["test_runs"]:
                        run["status"] = "pending"
                    return httpx.Response(200, json=pending)
                return httpx.Response(200, json=runs_completed[-1])
            client = self.client(handler)
            quick_poll = lambda c, r: evaluate.wait_for_result(c, r, seconds=1, interval=0)
            with patch.object(batch, "wait_for_result", side_effect=quick_poll):
                folder, response = batch.start_batch(client, base, suite, inputs, "agent_local", "branch_local", "baseline")
                self.assertEqual(batch.finalize(client, base, folder, response), 0)
                summary = evaluate.read_json(folder / "summary.json")
                self.assertEqual(len(summary["cases"]), 2)
                self.assertEqual(summary["overview"]["by_outcome"]["PASSED"], 2)
                self.assertIsNone(evaluate.read_json(base / ".batch-state.json")["pending"])
                posts_before = sum(m == "POST" for m, _ in calls)
                recovered, response = batch.recover(client, base, "latest")
                self.assertEqual(batch.finalize(client, base, recovered, response), 0)
                self.assertEqual(sum(m == "POST" for m, _ in calls), posts_before)
                folder2, response2 = batch.start_batch(client, base, suite, copy.deepcopy(originals), "agent_local", "branch_local", "repeat")
                self.assertEqual(batch.finalize(client, base, folder2, response2), 0)
                self.assertEqual(len(registrations), 2)
                self.assertEqual(len(runs_completed), 2)
                self.assertNotEqual(folder, folder2)

    def test_rejected_and_uncertain_posts_are_not_retried(self):
        suite, original_inputs = batch.load_inputs(batch.BASE, "tool_local", "01")
        for status, pending in [(401, False), (500, True)]:
            with self.subTest(status=status), tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp, redirect_stdout(StringIO()):
                base = Path(tmp)
                inputs = copy.deepcopy(original_inputs)
                evaluate.save_json(base / ".batch-state.json", {"registrations": {inputs[0]["signature"]: "test_local"}})
                calls = []
                def handler(req):
                    calls.append(req)
                    return httpx.Response(status, json={"detail": "Prepared test error"})
                client = self.client(handler)
                with self.assertRaises(ApiError):
                    batch.start_batch(client, base, suite, inputs, "agent_local", "branch_local", "error")
                self.assertEqual(len(calls), 1)
                self.assertEqual(bool(evaluate.read_json(base / ".batch-state.json")["pending"]), pending)
                if pending:
                    with self.assertRaisesRegex(ValueError, "pending"):
                        batch.start_batch(client, base, suite, inputs, "agent_local", "branch_local", "error")
                    self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
