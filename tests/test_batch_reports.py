"""Local report checks: no SDK, API calls or real results."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from batch_reports import generate_reports


def temporary_directory():
    # Keep temporary files inside the project for environments with a restricted TEMP directory.
    return tempfile.TemporaryDirectory(prefix="reports-", dir=Path(__file__).resolve().parent)


def make_input(number=1, optional=False, error=False):
    return {
        "case": {
            "id": f"{number:02d}-case", "name": f"Case {number}", "category": "catalog",
            "purpose": "Verify the information", "max_turns": 5,
            "tool": "list_courses", "tool_expectation": "optional" if optional else "required",
            "mock": {"file": "catalog.json", "is_error": error},
        },
        "response": {"status": "error", "code": "CATALOG_UNAVAILABLE"} if error else {
            "status": "ok", "total": 0, "courses": []
        },
        "payload": {}, "signature": f"hash-{number}", "test_id": f"test-{number}",
    }


def run(item, status="passed", grade="success", call_tool=True):
    messages = [{
        "role": "agent", "message": "Assistant response.",
        "agent_metadata": {"workflow_node_id": "information"},
        "tool_calls": [{"tool_name": "transfer_to_agent", "request_id": "system"}],
        "tool_results": [{"tool_name": "transfer_to_agent", "request_id": "system", "is_error": False,
                          "result_value": "Transition completed."}],
    }]
    if call_tool:
        messages[0]["tool_calls"].append({"tool_name": "list_courses", "request_id": "query"})
        messages[0]["tool_results"].append({
            "tool_name": "list_courses", "request_id": "query",
            "is_error": item["case"]["mock"]["is_error"],
            "result_value": json.dumps(item["response"]),
        })
    return {
        "test_id": item["test_id"], "test_run_id": "run-" + item["test_id"],
        "test_invocation_id": "suite-1", "agent_id": "agent-1", "branch_id": "main",
        "version_id": "v1", "ran_against_draft": False, "status": status,
        "condition_result": {"result": grade, "rationale": {"summary": "Criterion evaluated."}},
        "agent_responses": messages, "credits_used": 5,
    }


def suite(runs):
    return {"id": "suite-1", "agent_id": "agent-1", "branch_id": "main", "version_id": "v1",
            "ran_against_draft": False, "test_runs": runs}


class BatchReportsTests(unittest.TestCase):
    def generate(self, folder, runs, inputs):
        return generate_reports(Path(folder), suite(runs), inputs)

    def test_match_by_id_with_reversed_runs_and_written_files(self):
        items = [make_input(1), make_input(2)]
        runs = [run(items[1]), run(items[0])]
        runs[0]["condition_result"]["rationale"]["summary"] = "Second response."
        with temporary_directory() as folder:
            summary = self.generate(folder, runs, items)
            self.assertEqual([c["test_id"] for c in summary["cases"]], ["test-1", "test-2"])
            self.assertIn("Second response", summary["cases"][1]["rationale_text"])
            self.assertEqual(summary["overview"]["by_outcome"]["PASSED"], 2)
            self.assertEqual(summary["overview"]["reported_credits"], 10)
            self.assertEqual(summary["cases"][0]["nodes_seen"], ["information"])
            csv_path = Path(folder) / "summary.csv"
            self.assertTrue(csv_path.read_bytes().startswith(b"\xef\xbb\xbf"))
            with csv_path.open(encoding="utf-8-sig", newline="") as file:
                self.assertEqual(len(list(csv.DictReader(file, delimiter=";"))), 2)
            per_case = json.loads((Path(folder) / "cases/01-case/full-result.json").read_text("utf-8"))
            self.assertEqual(per_case["test_runs"][0]["test_id"], "test-1")
            self.assertIn("Assistant response", (Path(folder) / "cases/01-case/conversation.txt").read_text("utf-8"))

    def test_expected_tool_error_also_verifies_mock(self):
        item = make_input(error=True)
        with temporary_directory() as folder:
            case = self.generate(folder, [run(item)], [item])["cases"][0]
            self.assertEqual(case["outcome"], "PASSED")
            self.assertTrue(case["mock_confirmed"])

    def test_twenty_cases_generate_twenty_rows_and_folders(self):
        items = [make_input(i) for i in range(1, 21)]
        with temporary_directory() as folder:
            summary = self.generate(folder, [run(item) for item in reversed(items)], items)
            self.assertEqual(summary["overview"]["planned"], 20)
            self.assertEqual(summary["overview"]["by_outcome"]["PASSED"], 20)
            with (Path(folder) / "summary.csv").open(encoding="utf-8-sig", newline="") as file:
                self.assertEqual(len(list(csv.DictReader(file, delimiter=";"))), 20)
            self.assertEqual(len(list((Path(folder) / "cases").iterdir())), 20)

    def test_optional_tool_not_called_and_system_events(self):
        item = make_input(optional=True)
        with temporary_directory() as folder:
            case = self.generate(folder, [run(item, call_tool=False)], [item])["cases"][0]
            self.assertEqual(case["outcome"], "PASSED")
            self.assertEqual(case["evidence"], "NA")
            self.assertIsNone(case["mock_confirmed"])

    def test_unexecuted_tool_call_does_not_verify_mock(self):
        for optional in (False, True):
            item = make_input(optional=optional)
            response = run(item)
            response["agent_responses"][0]["tool_calls"][-1]["tool_has_been_called"] = False
            with self.subTest(optional=optional), temporary_directory() as folder:
                case = self.generate(folder, [response], [item])["cases"][0]
                self.assertFalse(case["tool_called"])
                self.assertEqual(case["outcome"], "PASSED" if optional else "REVIEW_EVIDENCE")
                self.assertEqual(case["evidence"], "NA" if optional else "INSUFFICIENT")

    def test_blocked_response_does_not_verify_mock_even_with_matching_json(self):
        for optional in (False, True):
            for call in (False, True):
                item = make_input(optional=optional)
                response = run(item)
                response["agent_responses"][0]["tool_calls"][-1]["tool_has_been_called"] = call
                response["agent_responses"][0]["tool_results"][-1]["is_blocked"] = True
                with self.subTest(optional=optional, call=call), temporary_directory() as folder:
                    case = self.generate(folder, [response], [item])["cases"][0]
                    self.assertEqual(case["outcome"], "REVIEW_EVIDENCE")
                    self.assertEqual(case["tool_called"], call)
                    self.assertFalse(case["mock_confirmed"])

    def test_missing_or_duplicate_run_is_inconclusive(self):
        item = make_input()
        for runs in ([], [run(item), run(item)]):
            with self.subTest(count=len(runs)), temporary_directory() as folder:
                summary = self.generate(folder, runs, [item])
                self.assertEqual(summary["cases"][0]["outcome"], "INCONCLUSIVE")
                self.assertEqual(summary["overview"]["decisive_coverage"], 0)
                self.assertIsNone(summary["overview"]["decisive_pass_rate"])

    def test_cancelled_batch_only_marks_missing_runs_cancelled(self):
        item = make_input()
        for runs, expected in (([], "CANCELLED"), ([run(item), run(item)], "INCONCLUSIVE"),
                               ([run(item)], "PASSED")):
            data = {**suite(runs), "cancelled": True}
            with self.subTest(count=len(runs)), temporary_directory() as folder:
                case = generate_reports(Path(folder), data, [item])["cases"][0]
                self.assertEqual(case["outcome"], expected)

    def test_wrong_mock_requires_review_even_with_positive_grade(self):
        for optional in (False, True):
            item = make_input(optional=optional)
            response = run(item)
            response["agent_responses"][0]["tool_results"][-1]["result_value"] = '{"other":"value"}'
            with self.subTest(optional=optional), temporary_directory() as folder:
                case = self.generate(folder, [response], [item])["cases"][0]
                self.assertEqual(case["outcome"], "REVIEW_EVIDENCE")
                self.assertFalse(case["mock_confirmed"])

    def test_failed_cancelled_and_pending_runs(self):
        item = make_input()
        for status, grade, expected in (("failed", "failure", "FAILED"),
                                        ("cancelled", "unknown", "CANCELLED"),
                                        ("pending", "unknown", "INCONCLUSIVE")):
            with self.subTest(status=status), temporary_directory() as folder:
                case = self.generate(folder, [run(item, status, grade)], [item])["cases"][0]
                self.assertEqual(case["outcome"], expected)

    def test_metadata_new_version_draft_and_unexpected_ids(self):
        item = make_input()
        primary = run(item)
        primary.update({"version_id": "v2", "ran_against_draft": True, "future_field": {"new": True}})
        extra = run(make_input(2))
        del extra["credits_used"]
        with temporary_directory() as folder:
            summary = self.generate(folder, [primary, extra], [item])
            alerts = " ".join(summary["overview"]["alerts"])
            self.assertIn("version", alerts)
            self.assertIn("draft", alerts)
            self.assertIn("Unexpected", alerts)
            self.assertEqual(summary["overview"]["total_without_credits"], 1)
            raw = json.loads((Path(folder) / "full-result.json").read_text("utf-8"))
            self.assertTrue(raw["test_runs"][0]["future_field"]["new"])
            self.assertEqual(summary["cases"][0]["version_id"], "v2")

    def test_tool_call_without_response_cannot_pass(self):
        item = make_input()
        response = run(item)
        response["agent_responses"][0]["tool_results"] = []
        with temporary_directory() as folder:
            case = self.generate(folder, [response], [item])["cases"][0]
            self.assertEqual(case["outcome"], "REVIEW_EVIDENCE")

    def test_invalid_paths_are_rejected_before_writing(self):
        for identifier in ("../outside", "/absolute", "C:\\outside", "CON", "..", "case/"):
            item = make_input()
            item["case"]["id"] = identifier
            with self.subTest(identifier=identifier), temporary_directory() as folder:
                with self.assertRaises(ValueError):
                    self.generate(folder, [], [item])
                self.assertEqual(list(Path(folder).iterdir()), [])
        items = [make_input(1), make_input(2)]
        items[0]["case"]["id"], items[1]["case"]["id"] = "CASE", "case"
        with temporary_directory() as folder:
            with self.assertRaises(ValueError):
                self.generate(folder, [], items)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
