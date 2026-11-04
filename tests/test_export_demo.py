"""Synthetic publication tests without credentials or ElevenLabs calls."""

from collections import Counter
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "scripts" / "export_demo.py"
spec = importlib.util.spec_from_file_location("export_demo", MODULE)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def fixture_raw():
    call = {"request_id": "request_original_abc123", "tool_id": "tool_original_abc123", "tool_name": "notify_condition_1", "tool_has_been_called": True,
               "params_as_json": '{"email":"person@example.test","api_key":"synthetic-secret"}', "future_field": "do-not-publish"}
    response = {"request_id": call["request_id"], "tool_name": call["tool_name"], "tool_has_been_called": True,
               "is_blocked": False, "result_value": '{"workspace_id":"workspace_original_abc123","token":"synthetic-secret"}',
               "result": {"steps": [{"requests": [call]}]}}
    return {"invocation_id": "suite_original_abc123", "test_id": "test_original_abc123", "unknown": "do-not-publish", "test_runs": [{
        "test_run_id": "run_original_abc123", "test_id": "test_original_abc123", "agent_id": "agent_original_abc123",
        "branch_id": "agtbrch_original_abc123", "version_id": "agtvrsn_original_abc123", "ran_against_draft": False,
        "status": "success", "credits_used": 42,
        "metadata": {"ran_by_user_email": "person@example.test", "workspace_id": "workspace_original_abc123", "authorization": "synthetic-secret"},
        "test_info": {"tool_mock_overrides": {"tool_original_abc123": [{"mock_result": '{"token":"synthetic-secret"}'}]}},
        "condition_result": {"result": "success", "rationale": {"summary": "Criteria met.", "messages": [], "future_field": "do-not-publish"}},
        "charging": {"llm_charge": 39, "platform_charge": 3, "future_field": "do-not-publish"},
        "agent_responses": [
            {"role": "user", "message": "What is the price?", "user_identifier": "person@example.test"},
            {"role": "agent", "message": "The monthly fee is BRL 220.", "time_in_call_secs": 2.5, "producing_llm": "test-model",
             "agent_metadata": {"agent_id": "agent_original_abc123"}, "tool_calls": [call, call], "tool_results": [response],
             "llm_usage": {"model_usage": {"test-model": {"input": {"tokens": 20}}}}},
            {"role": "agent", "message": "Any other questions?", "tool_calls": [{**call, "request_id": "request_second_abc123"}]},
        ],
    }]}


def create_source(root):
    source = root / "local"
    folder = source / "batches" / "batch_20260101T000000Z_example"
    case = {"case_id": "01-price", "name": "Price", "category": "Information", "purpose": "development", "signature": "a" * 64,
            "outcome": "PASSED", "platform_status": "success", "rationale_text": "Criteria met.",
            "test_id": "test_original_abc123", "test_run_id": "run_original_abc123", "agent_id": "agent_original_abc123", "credits_used": 42,
            "ran_against_draft": False, "nodes_seen": ["node_original_abc123"], "future_field": "do-not-publish"}
    overview = {"planned": 1, "by_outcome": {k: int(k == "PASSED") for k in demo.OUTCOMES}, "decisive_pass_rate": 1,
             "decisive_coverage": 1, "reported_credits": 42, "total_without_credits": 0, "alerts": [], "future_field": "do-not-publish"}
    demo.write_json(folder / "manifest.json", {"label": "Example", "created_at_utc": "2026-01-01T00:00:00Z", "agent_id": case["agent_id"], "cases": [case["case_id"]], "future_field": "do-not-publish"})
    demo.write_json(folder / "summary.json", {"overview": overview, "cases": [case]})
    demo.write_json(folder / "inputs.json", [{"case": {"id": case["case_id"], "scenario": "Ask for the price.", "success_criteria": ["States BRL 220."], "future_field": "do-not-publish"},
         "response": {"status": "ok", "total": 0, "courses": [], "authorization": "synthetic-secret"}, "payload": {"token": "synthetic-secret"}}])
    case_folder = folder / "cases" / case["case_id"]
    demo.write_json(case_folder / "full-result.json", fixture_raw())
    (case_folder / "conversation.txt").write_text("USER: What is the price?\nAGENT: The monthly fee is BRL 220.\n", encoding="utf-8")
    (source / ".env").write_text("MUST_NOT_BE_READ=synthetic-secret\n", encoding="utf-8")
    return source, folder


class DemoExportTests(unittest.TestCase):
    def test_translation_provenance_survives_export_without_inventing_it(self):
        metadata = {
            "source_language": "pt-BR", "content_language": "en",
            "translation_note": "English translation of an original run; not a new evaluation.",
        }
        raw = fixture_raw()
        self.assertFalse(set(metadata) & set(demo.project_result(raw)))
        self.assertFalse(set(metadata) & set(demo.project_manifest({})))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, folder = create_source(root)
            manifest_path = folder / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            demo.write_json(manifest_path, {**manifest, **metadata})
            raw.update(metadata)
            demo.write_json(folder / "cases/01-price/full-result.json", raw)
            destination = root / "publishable"
            demo.export(source, destination)
            exported = destination / "batches" / folder.name
            for relative in ("manifest.json", "cases/01-price/full-result.json"):
                data = json.loads((exported / relative).read_text(encoding="utf-8"))
                for key, value in metadata.items():
                    self.assertEqual(data[key], value)
            self.assertNotIn("translation_note", demo.project_manifest({"translation_note": {"private": "value"}}))

    def test_projection_omits_metadata_and_arbitrary_nested_json(self):
        raw = fixture_raw()
        output = demo.project_result(raw)
        serialized = json.dumps(output)
        for forbidden in ("ran_by_user_email", "workspace_id", "person@example.test", "synthetic-secret", "do-not-publish", "params_as_json", "tool_mock_overrides", "agent_metadata"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(output["test_runs"][0]["credits_used"], 42)
        self.assertEqual(output["test_runs"][0]["condition_result"]["result"], "success")
        self.assertEqual(output["test_runs"][0]["charging"]["llm_charge"], 39)

    def test_deterministic_aliases_preserve_associations(self):
        raw = fixture_raw()
        output = demo.project_result(raw)
        self.assertEqual(output["test_id"], output["test_runs"][0]["test_id"])
        call = output["test_runs"][0]["agent_responses"][1]["tool_calls"][0]
        response = output["test_runs"][0]["agent_responses"][1]["tool_results"][0]
        self.assertEqual(call["request_id"], response["request_id"])
        self.assertEqual(demo.alias_id(raw["test_id"]), output["test_id"])
        self.assertNotEqual(demo.alias_id("a"), demo.alias_id("b"))

    def test_trun_in_header_uses_same_alias_as_json(self):
        identifier = "trun_0123456789abcdefghijklmnop"
        raw = fixture_raw()
        raw["test_runs"][0]["test_run_id"] = identifier
        expected = demo.project_result(raw)["test_runs"][0]["test_run_id"]
        header = demo.text(f"Run: {identifier}\n")
        self.assertEqual(header, f"Run: {expected}\n")
        self.assertNotIn(identifier, header)

    def test_deduplication_and_counts_ignore_nested_tools(self):
        raw = fixture_raw()
        expected = Counter({"notify_condition_1": 2})
        self.assertEqual(demo.call_count(raw), expected)
        self.assertEqual(demo.call_count(demo.project_result(raw)), expected)

    def test_result_based_confirmation_is_preserved(self):
        raw = fixture_raw()
        m = raw["test_runs"][0]["agent_responses"][1]
        for call in m["tool_calls"]:
            call.pop("tool_has_been_called", None)
        self.assertEqual(demo.call_count(raw), demo.call_count(demo.project_result(raw)))

    def test_text_redacts_email_credentials_urls_paths_and_ids(self):
        original = r"Contact person@example.test, sk_0123456789abcdefghijkl C:\Users\person\test.txt /home/person/test https://example.test/token=secret agent_original_abc123 123e4567-e89b-12d3-a456-426614174000"
        clean = demo.text(original)
        for forbidden in ("person@example.test", "0123456789", "C:\\Users", "/home/", "https://", "agent_original_abc123", "123e4567-e89b"):
            self.assertNotIn(forbidden, clean)
        self.assertIn("demo_", clean)

    def test_export_preserves_grades_criteria_and_conversations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, folder = create_source(root)
            destination = root / "publishable"
            self.assertEqual(demo.export(source, destination), {"batches": 1, "cases": 1})
            publishable = destination / "batches" / folder.name
            summary = json.loads((publishable / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["overview"]["by_outcome"]["PASSED"], 1)
            self.assertEqual(summary["overview"]["reported_credits"], 42)
            self.assertEqual(summary["cases"][0]["signature"], "a" * 64)
            entry = json.loads((publishable / "inputs.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(entry["case"]["success_criteria"], ["States BRL 220."])
            self.assertEqual((publishable / "cases/01-price/conversation.txt").read_text(encoding="utf-8"), "USER: What is the price?\nAGENT: The monthly fee is BRL 220.\n")
            all_text = "\n".join(p.read_text(encoding="utf-8") for p in publishable.rglob("*") if p.is_file())
            for forbidden in ("synthetic-secret", "do-not-publish", "person@example.test", "test_original_abc123"):
                self.assertNotIn(forbidden, all_text)
            self.assertFalse((destination / ".env").exists())
            self.assertTrue((source / ".env").exists())

    def test_overlapping_or_existing_destination_is_rejected_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, folder = create_source(root)
            original = (folder / "summary.json").read_bytes()
            for destination in (source, source / "child", root):
                with self.assertRaises(ValueError):
                    demo.export(source, destination)
            destination = root / "publishable"
            demo.export(source, destination)
            with self.assertRaises(ValueError):
                demo.export(source, destination)
            self.assertEqual(original, (folder / "summary.json").read_bytes())

    def test_case_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, folder = create_source(root)
            p = folder / "summary.json"
            summary = json.loads(p.read_text(encoding="utf-8"))
            summary["cases"][0]["case_id"] = "../outside"
            demo.write_json(p, summary)
            with self.assertRaises(ValueError):
                demo.export(source, root / "publishable")
            self.assertFalse((root / "publishable/batches").exists())


if __name__ == "__main__":
    unittest.main()
