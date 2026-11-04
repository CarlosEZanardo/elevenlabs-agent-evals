"""Dashboard report loading: associations, missing timestamp and file boundaries."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard_data import discover_batches, read_detail


def temporary_directory():
    return tempfile.TemporaryDirectory(prefix="dashboard-", dir=Path(__file__).resolve().parent)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def example_case():
    return {
        "case_id": "01-case", "name": "Catalog case", "category": "information",
        "signature": "hash1", "outcome": "PASSED", "credits_used": 12,
        "test_id": "test-1", "test_run_id": "run-1", "version_id": "version-1",
        "ran_against_draft": False, "nodes_seen": ["information"],
    }


def create_batch(base, name="batch_20261030T000627Z_abc", timestamp="2026-10-30T00:06:27+00:00", cases=None):
    folder = base / "batches" / name
    rows = [example_case()] if cases is None else cases
    save(folder / "manifest.json", {
        "label": "Controlled batch", "created_at_utc": timestamp,
        "suite_version": "1.1", "dataset_signature": "dataset-1",
        "invocation_id": "suite-1", "phase": "completed",
    })
    save(folder / "summary.json", {
        "overview": {
            "planned": len(rows), "by_outcome": {
                "PASSED": len(rows), "FAILED": 0, "REVIEW_EVIDENCE": 0,
                "INCONCLUSIVE": 0, "CANCELLED": 0,
            },
            "decisive_pass_rate": 1.0, "decisive_coverage": 1.0,
            "reported_credits": sum(row.get("credits_used", 0) for row in rows
                                       if isinstance(row.get("credits_used"), (int, float))),
            "total_without_credits": 0, "alerts": [],
        }, "cases": rows,
    })
    return folder


def create_detail(folder, messages=None, runs=None):
    save(folder / "inputs.json", [{"case": {
        "id": "01-case", "scenario": "Ask for the price and accept the explanation.",
        "success_criteria": ["State the correct price.", "Do not guarantee availability."],
    }}])
    case = folder / "cases" / "01-case"
    case.mkdir(parents=True, exist_ok=True)
    (case / "conversation.txt").write_text("agent: Public response.\n", encoding="utf-8")
    if runs is None:
        runs = [{"test_run_id": "run-1", "test_id": "test-1",
                 "agent_responses": messages or [],
                 "charging": {"llm_usage": {"model_usage": {"evaluator-model": {}}}}}]
    save(case / "full-result.json", {"invocation_id": "suite-1", "test_runs": runs})
    return case


class DashboardDataTests(unittest.TestCase):
    def test_translation_provenance_is_optional_and_read_from_manifest(self):
        with temporary_directory() as temp:
            base = Path(temp)
            folder = create_batch(base)
            batches, _ = discover_batches(base)
            self.assertIsNone(batches[0]["translation_note"])
            manifest_path = folder / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            metadata = {
                "source_language": "pt-BR", "content_language": "en",
                "translation_note": "English translation of an original run; not a new evaluation.",
            }
            manifest.update(metadata)
            save(manifest_path, manifest)
            batches, warnings = discover_batches(base)
            self.assertFalse(warnings)
            for key, value in metadata.items():
                self.assertEqual(batches[0][key], value)

    def test_multiple_batch_inventory_preserves_outcomes(self):
        with temporary_directory() as temp:
            base = Path(temp)
            create_batch(base, "batch_20261001T000000Z_a", "2026-10-01T00:00:00Z")
            second = example_case()
            second.update(case_id="02-case", credits_used=24)
            create_batch(base, "batch_20261002T000000Z_b", "2026-10-02T00:00:00Z", [example_case(), second])
            batches, warnings = discover_batches(base)
            self.assertEqual(len(batches), 2)
            self.assertEqual(sum(len(batch["cases"]) for batch in batches), 3)
            self.assertEqual(sum(batch["overview"]["reported_credits"] for batch in batches), 48)
            self.assertFalse(warnings)
            self.assertEqual(batches[0]["batch_id"], "batch_20261002T000000Z_b")
            self.assertEqual(batches[0]["overview"]["by_outcome"]["PASSED"], 2)
            self.assertNotIn("human_review", batches[0])
            self.assertNotIn("human_evaluation", batches[0]["cases"][0])

    def test_discovery_reads_only_manifest_and_summary_and_copies_rows(self):
        with temporary_directory() as temp:
            base = Path(temp)
            create_batch(base)
            original = Path.read_text

            def read(path, *args, **kwargs):
                self.assertIn(path.name, {"manifest.json", "summary.json"})
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", autospec=True, side_effect=read):
                batches, warnings = discover_batches(base)
            self.assertFalse(warnings)
            row = batches[0]["cases"][0]
            self.assertEqual(row["batch_id"], batches[0]["batch_id"])
            self.assertEqual(row["batch_label"], "Controlled batch")
            self.assertEqual(batches[0]["versions"], ["version-1"])
            self.assertIs(batches[0]["draft"], False)
            row["nodes_seen"].append("in-memory-mutation-only")
            again, _ = discover_batches(base / "batches")
            self.assertEqual(again[0]["cases"][0]["nodes_seen"], ["information"])

    def test_sorting_uses_manifest_date_with_folder_name_fallback(self):
        with temporary_directory() as temp:
            base = Path(temp)
            create_batch(base, "batch_20260101T000000Z_a", "2026-12-01T00:00:00Z")
            create_batch(base, "batch_20261101T000000Z_b", "invalid-date")
            create_batch(base, "batch_20261001T000000Z_c", "2026-01-01T00:00:00Z")
            batches, _ = discover_batches(base)
            self.assertEqual([l["batch_id"] for l in batches], [
                "batch_20260101T000000Z_a", "batch_20261101T000000Z_b", "batch_20261001T000000Z_c",
            ])

    def test_partial_files_and_missing_data_do_not_become_zero(self):
        with temporary_directory() as temp:
            base = Path(temp)
            folder = create_batch(base)
            (folder / "manifest.json").write_text('{"label":', encoding="utf-8")
            save(folder / "summary.json", {"cases": [{"case_id": "01-case"}]})
            batches, warnings = discover_batches(base)
            self.assertTrue(warnings)
            batch = batches[0]
            self.assertIsNone(batch["label"])
            self.assertIsNone(batch["overview"]["decisive_pass_rate"])
            self.assertIsNone(batch["overview"]["by_outcome"]["PASSED"])
            self.assertIsNone(batch["overview"]["reported_credits"])
            self.assertIsNone(batch["cases"][0]["outcome"])
            self.assertIsNone(batch["cases"][0]["credits_used"])
            self.assertIsNone(batch["draft"])
            (folder / "summary.json").unlink()
            again, warnings = discover_batches(base)
            self.assertTrue(warnings)
            self.assertEqual(again[0]["cases"], [])

    def test_measured_zero_and_unknown_remain_distinct(self):
        with temporary_directory() as temp:
            base = Path(temp)
            folder = create_batch(base)
            save(folder / "summary.json", {
                "overview": {"planned": 1, "by_outcome": {"PASSED": 0},
                               "decisive_pass_rate": 0, "decisive_coverage": 0,
                               "reported_credits": 0, "total_without_credits": 1},
                "cases": [{"case_id": "01-case", "outcome": "INCONCLUSIVE", "credits_used": None}],
            })
            batches, _ = discover_batches(base)
            v = batches[0]["overview"]
            self.assertEqual(v["decisive_pass_rate"], 0)
            self.assertEqual(v["by_outcome"]["PASSED"], 0)
            self.assertIsNone(v["by_outcome"]["FAILED"])
            self.assertEqual(v["reported_credits"], 0)
            self.assertIsNone(batches[0]["cases"][0]["credits_used"])

    def test_detail_associates_run_agent_models_and_top_level_calls(self):
        with temporary_directory() as temp:
            base = Path(temp)
            folder = create_batch(base)
            messages = [
                {"role": "agent", "message": "Public response.", "producing_llm": "generating-model",
                 "tool_calls": [
                     {"tool_name": "list_courses", "request_id": "q", "tool_has_been_called": True},
                     {"tool_name": "notify_condition_1_met", "request_id": "e", "tool_has_been_called": True},
                     {"tool_name": "blocked", "request_id": "b", "tool_has_been_called": False},
                     {"tool_name": "legacy", "request_id": "a"},
                     {"tool_name": "unconfirmed", "request_id": "x"}],
                 "tool_results": [
                     {"tool_name": "legacy", "request_id": "a", "tool_has_been_called": True},
                     {"tool_name": "notify_condition_1_met", "request_id": "e", "tool_has_been_called": True,
                      "result": {"steps": [{"nested_tools": {"requests": [
                          {"tool_name": "transfer_to_agent", "tool_has_been_called": True}]}}]}}]},
                {"role": "user", "message": "Question.", "producing_llm": "customer-model",
                 "llm_usage": {"model_usage": {"customer-usage-model": {}}},
                 "tool_calls": [{"tool_name": "customer-fake-call", "tool_has_been_called": True}]},
                {"role": "agent", "message": "Follow-up.", "tool_results": 42,
                 "llm_usage": {"model_usage": {"usage-model": {}},
                               "detailed_model_usage": [{"config": {"model": "config-model"}}]},
                 "tool_calls": [
                     {"tool_name": "list_courses", "request_id": "q", "tool_has_been_called": True},
                     {"tool_name": "no-id", "tool_has_been_called": True},
                     {"tool_name": "no-id", "tool_has_been_called": True}]},
            ]
            create_detail(folder, runs=[
                {"test_run_id": "other-run", "agent_responses": [{"role": "agent", "message": "Wrong."}]},
                {"test_run_id": "run-1", "test_id": "test-1", "agent_responses": messages,
                 "charging": {"model_usage": {"evaluator-model": {}}}},
            ])
            detail = read_detail(base, folder.name, "01-case")
            self.assertEqual(detail["messages"], messages)
            self.assertEqual(detail["models"], ["config-model", "generating-model", "usage-model"])
            self.assertEqual(detail["tool_counts"], {
                "legacy": 1, "list_courses": 1, "notify_condition_1_met": 1, "no-id": 2,
            })
            self.assertIn("price", detail["criteria"][0])
            self.assertIn("Ask", detail["script"])
            self.assertIn("Public response", detail["conversation"])
            self.assertIs(detail["warning"], detail["warnings"])
            self.assertTrue(any("without execution evidence" in a for a in detail["warnings"]))

    def test_repeated_transitions_are_counted_without_reclassifying_outcome(self):
        with temporary_directory() as temp:
            base = Path(temp)
            folder = create_batch(base)
            messages = [
                {"role": "agent", "producing_llm": "generating-model", "tool_calls": [{
                    "tool_name": "notify_condition_1_met", "request_id": "first",
                    "tool_has_been_called": True}]},
                {"role": "agent", "producing_llm": "generating-model", "tool_calls": [{
                    "tool_name": "notify_condition_1_met", "request_id": "second",
                    "tool_has_been_called": True}]},
                {"role": "agent", "producing_llm": "generating-model", "message": "Correct response."},
            ]
            create_detail(folder, messages=messages)
            detail = read_detail(base, folder.name, "01-case")
            self.assertFalse(detail["warnings"])
            self.assertEqual(detail["case"]["outcome"], "PASSED")
            self.assertEqual(detail["tool_counts"]["notify_condition_1_met"], 2)
            self.assertEqual(detail["models"], ["generating-model"])
            self.assertNotIn("evaluator-model", detail["models"])

    def test_path_traversal_reserved_identifiers_and_unauthorized_cases(self):
        with temporary_directory() as temp:
            base = Path(temp)
            folder = create_batch(base)
            create_detail(folder)
            for batch_id, case_id in [("../outside", "01-case"), (folder.name, "../01-case"),
                                     (folder.name, "C:\\outside"), (folder.name, "CON"),
                                     (folder.name, "02-unlisted")]:
                with self.subTest(batch=batch_id, case=case_id):
                    detail = read_detail(base, batch_id, case_id)
                    self.assertTrue(detail["warnings"])
                    self.assertIsNone(detail["case"])
                    self.assertEqual(detail["full_result"], {})

    def test_symlink_outside_root_is_not_read(self):
        with temporary_directory() as temp:
            base = Path(temp) / "project"
            folder = create_batch(base)
            create_detail(folder)
            outside = Path(temp) / "not-allowed.json"
            save(outside, {"secret": "must-not-be-read"})
            target = folder / "cases" / "01-case" / "full-result.json"
            target.unlink()
            try:
                target.symlink_to(outside)
            except OSError as exc:
                self.skipTest("Symlink creation requires additional privileges on this Windows system.")
            detail = read_detail(base, folder.name, "01-case")
            self.assertEqual(detail["full_result"], {})
            self.assertTrue(detail["warnings"])
            # Discovery must also reject batch-folder links outside the root.
            external = Path(temp) / "batch_external"
            external.mkdir()
            (base / "batches" / "batch_symlink").symlink_to(external, target_is_directory=True)
            batches, warnings = discover_batches(base)
            self.assertEqual(len(batches), 1)
            self.assertTrue(any("batch_symlink" in a for a in warnings))

    def test_resolved_target_outside_root_is_blocked_without_symlink_privileges(self):
        # Simulate the link target resolved by Windows to exercise the
        # boundary check without requiring symlink privileges.
        with temporary_directory() as temp:
            base = Path(temp) / "project"
            folder = create_batch(base)
            case = create_detail(folder)
            target = case / "full-result.json"
            outside = Path(temp) / "outside.json"
            save(outside, {"secret": "must not be opened"})
            original_resolve, original_read = Path.resolve, Path.read_text

            def resolve(path, *args, **kwargs):
                if path == target:
                    return original_resolve(outside)
                return original_resolve(path, *args, **kwargs)

            def read(path, *args, **kwargs):
                self.assertNotEqual(path, original_resolve(outside))
                return original_read(path, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True, side_effect=resolve), \
                    patch.object(Path, "read_text", autospec=True, side_effect=read):
                detail = read_detail(base, folder.name, "01-case")
            self.assertEqual(detail["full_result"], {})
            self.assertTrue(detail["warnings"])

    def test_corrupt_json_and_unexpected_structures_do_not_crash_detail(self):
        with temporary_directory() as temp:
            base = Path(temp)
            folder = create_batch(base)
            case = create_detail(folder)
            (folder / "inputs.json").write_text("incomplete", encoding="utf-8")
            (case / "full-result.json").write_text("{", encoding="utf-8")
            detail = read_detail(base, folder.name, "01-case")
            self.assertEqual(detail["case"]["outcome"], "PASSED")
            self.assertTrue(detail["warnings"])
            self.assertEqual(detail["messages"], [])
            save(case / "full-result.json", {"test_runs": {"wrong": True}})
            self.assertTrue(read_detail(base, folder.name, "01-case")["warnings"])

    def test_duplicates_and_case_insensitive_folder_collisions_are_ambiguous(self):
        with temporary_directory() as temp:
            base = Path(temp)
            first, second = example_case(), example_case()
            second["case_id"] = "01-CASE"
            folder = create_batch(base, cases=[first, second])
            batches, warnings = discover_batches(base)
            self.assertEqual(batches[0]["cases"], [])
            self.assertTrue(warnings)
            detail = read_detail(base, folder.name, "01-case")
            self.assertIsNone(detail["case"])

    def test_mixed_draft_states_and_invalid_values_remain_explicit(self):
        with temporary_directory() as temp:
            base = Path(temp)
            first, second = example_case(), example_case()
            second.update(case_id="02-case", ran_against_draft=True, version_id="version-2",
                           credits_used="unmeasured", category={"invalid": True})
            create_batch(base, cases=[first, second])
            batches, warnings = discover_batches(base)
            self.assertIs(batches[0]["draft"], True)
            self.assertEqual(batches[0]["versions"], ["version-1", "version-2"])
            self.assertIsNone(batches[0]["cases"][1]["credits_used"])
            self.assertIsNone(batches[0]["cases"][1]["category"])
            self.assertTrue(any("draft and published" in a for a in warnings))


if __name__ == "__main__":
    unittest.main()
