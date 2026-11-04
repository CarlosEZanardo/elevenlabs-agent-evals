"""Local suite reports: platform grading and mock evidence.

This module makes no network requests and calls no grader. Grading results
and rationales are supplied by the ElevenLabs response.
"""

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


OUTCOMES = ("PASSED", "FAILED", "REVIEW_EVIDENCE", "INCONCLUSIVE", "CANCELLED")
FIELDS = (
    "case_id", "name", "category", "purpose", "signature", "outcome",
    "platform_status", "platform_evaluation", "evidence", "tool_called",
    "mock_confirmed", "rationale_text", "test_id", "test_run_id", "invocation_id",
    "agent_id", "branch_id", "version_id", "ran_against_draft", "credits_used", "nodes_seen",
)
CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
}


def _save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _list(value):
    return value if isinstance(value, list) else []


def _metadata(run, data, field):
    value = run.get(field)
    return data.get(field) if value is None else value


def _validate_inputs(inputs):
    ids = set()
    for entry in inputs:
        case = entry["case"]
        identifier = case["id"]
        if (not isinstance(identifier, str) or not CASE_ID.fullmatch(identifier)
                or identifier.upper() in WINDOWS_RESERVED):
            raise ValueError("Invalid case ID for a local folder.")
        if identifier.casefold() in ids:
            raise ValueError("Duplicate case IDs would overwrite reports.")
        ids.add(identifier.casefold())
        if case["tool_expectation"] not in ("required", "optional"):
            raise ValueError("Unknown tool expectation.")
        if not isinstance(case["mock"]["is_error"], bool):
            raise ValueError("mock.is_error must be a boolean.")


def _events(run, field):
    return [event for message in _list(run.get("agent_responses"))
            if isinstance(message, dict) for event in _list(message.get(field))
            if isinstance(event, dict)]


def _evidence(run, entry):
    case = entry["case"]
    name = case["tool"]
    calls = [t for t in _events(run, "tool_calls")
                if t.get("tool_name") == name and t.get("tool_has_been_called") is not False]
    tool_results = [t for t in _events(run, "tool_results") if t.get("tool_name") == name]
    if any(t.get("is_blocked") is True for t in tool_results):
        return bool(calls), False, "INSUFFICIENT", "A tool response was blocked; the mock was not verified."
    if not calls:
        if case["tool_expectation"] == "optional":
            return False, None, "NA", "The optional tool was not called."
        return False, False, "INSUFFICIENT", "The required tool was not called."

    # Verify the expected response even when the scenario expects a tool error.
    correct = bool(tool_results)
    for response in tool_results:
        try:
            correct = correct and (
                response.get("is_error", False) is case["mock"]["is_error"]
                and json.loads(response.get("result_value", "")) == entry["response"]
            )
        except (ValueError, TypeError):
            correct = False

    # A correct response cannot hide another call with a missing or incorrect mock response.
    called_ids = {t["request_id"] for t in calls if t.get("request_id")}
    returned_ids = {t["request_id"] for t in tool_results if t.get("request_id")}
    if called_ids:
        correct = correct and called_ids.issubset(returned_ids)
    else:
        correct = correct and len(tool_results) >= len(calls)
    text = ("Tool call and mock response confirmed." if correct
             else "The tool was called, but its results do not verify the expected mock.")
    return True, correct, "CONFIRMED" if correct else "INSUFFICIENT", text


def _rationale(run):
    condition = run.get("condition_result") or {}
    rationale = condition.get("rationale") or {}
    if isinstance(rationale, str):
        return rationale
    parts = [rationale.get("summary"), *_list(rationale.get("messages"))]
    return " | ".join(p for p in parts if isinstance(p, str) and p.strip())


def _nodes_seen(run):
    nodes = []
    if run.get("workflow_node_id"):
        nodes.append(str(run["workflow_node_id"]))
    for message in _list(run.get("agent_responses")):
        if not isinstance(message, dict):
            continue
        metadata = message.get("agent_metadata") or {}
        if isinstance(metadata, dict) and metadata.get("workflow_node_id"):
            nodes.append(str(metadata["workflow_node_id"]))
    return list(dict.fromkeys(nodes))  # Observation only; never used to pass or fail a case.


def _row(entry, runs, data, duplicate_test_id=False):
    case = entry["case"]
    row = {field: None for field in FIELDS}
    row.update({
        "case_id": case["id"], "name": case.get("name"),
        "category": case.get("category"), "purpose": case.get("purpose"),
        "signature": entry.get("signature"), "test_id": entry.get("test_id"),
        "invocation_id": data.get("id"), "outcome": "INCONCLUSIVE",
        "evidence": "INCONCLUSIVE", "tool_called": False, "nodes_seen": [],
        "agent_id": data.get("agent_id"), "branch_id": data.get("branch_id"),
        "version_id": data.get("version_id"), "ran_against_draft": data.get("ran_against_draft"),
    })
    if duplicate_test_id or len(runs) != 1:
        if not duplicate_test_id and not runs and data.get("cancelled") is True:
            row["outcome"] = "CANCELLED"
            row["rationale_text"] = "The batch was cancelled and no run was returned for this test."
            return row
        row["rationale_text"] = (
            "The same test_id was assigned to multiple planned cases." if duplicate_test_id
            else "No run was returned for this test." if not runs
            else "Multiple runs were returned for this test; the association is ambiguous."
        )
        return row

    run = runs[0]
    condition = run.get("condition_result") or {}
    status, grade = run.get("status"), condition.get("result")
    call, mock, evidence, detail = _evidence(run, entry)
    if status == "cancelled":
        outcome = "CANCELLED"
    elif status == "passed" and grade == "success":
        outcome = "PASSED" if evidence in ("CONFIRMED", "NA") else "REVIEW_EVIDENCE"
    elif status == "failed" and grade == "failure":
        outcome = "FAILED"
    else:
        outcome = "INCONCLUSIVE"
    row.update({
        "outcome": outcome, "platform_status": status,
        "platform_evaluation": grade, "evidence": evidence,
        "tool_called": call, "mock_confirmed": mock,
        "rationale_text": " | ".join(filter(None, [_rationale(run), detail])),
        "test_run_id": run.get("test_run_id"), "credits_used": run.get("credits_used"),
        "nodes_seen": _nodes_seen(run),
    })
    for field in ("agent_id", "branch_id", "version_id", "ran_against_draft"):
        row[field] = _metadata(run, data, field)
    return row


def _alerts(data, runs, expected, counts):
    alerts = []
    unexpected = sorted({str(r.get("test_id", "<missing>")) for r in runs
                          if r.get("test_id") not in expected})
    if unexpected:
        alerts.append("Unexpected test IDs in the response: " + ", ".join(unexpected))
    duplicates = sorted(str(t) for t, n in counts.items() if n > 1)
    if duplicates:
        alerts.append("Duplicate test IDs in the inputs: " + ", ".join(duplicates))
    versions = {str(data["version_id"])} if data.get("version_id") else set()
    versions.update(str(r["version_id"]) for r in runs if r.get("version_id"))
    if len(versions) > 1:
        alerts.append("Multiple versions reported in this batch: " + ", ".join(sorted(versions)))
    drafts = [_metadata(r, data, "ran_against_draft") for r in runs]
    if True in drafts:
        alerts.append("A run has ran_against_draft=true; check the evaluated target.")
    if True in drafts and False in drafts:
        alerts.append("The batch mixes draft and published runs.")
    if runs and any(not _metadata(r, data, "version_id") for r in runs):
        alerts.append("The agent version was not reported for every run.")
    if runs and any(not isinstance(v, bool) for v in drafts):
        alerts.append("The draft flag was not reported for every run.")
    return alerts


def _conversation(entry, runs):
    lines = ["Ponte Idiomas — text evaluation", "Case: " + entry["case"]["id"], ""]
    if not runs:
        lines.append("No conversation was returned for this case.")
    for run in runs:
        lines.append("Run: " + str(run.get("test_run_id", "not reported")))
        for message in _list(run.get("agent_responses")):
            if not isinstance(message, dict):
                continue
            if message.get("message"):
                lines.append(str(message.get("role", "?")) + ": " + str(message["message"]))
            for field, label in (("tool_calls", "call"), ("tool_results", "response")):
                for event in _list(message.get(field)):
                    if isinstance(event, dict):
                        lines.append("  [" + label + ": " + str(event.get("tool_name", "?")) + "]")
    return "\n".join(lines)


def generate_reports(folder: Path, data: dict, inputs: list[dict]) -> dict:
    """Generate local files; match every planned row by test_id."""
    _validate_inputs(inputs)  # Validate paths before creating any file.
    folder = Path(folder)
    runs = [r for r in _list(data.get("test_runs")) if isinstance(r, dict)]
    index = defaultdict(list)
    for run in runs:
        index[run.get("test_id")].append(run)
    counts = Counter(e.get("test_id") for e in inputs)
    lines = [_row(e, index[e.get("test_id")], data, counts[e.get("test_id")] > 1)
              for e in inputs]
    outcome_counts = Counter(row["outcome"] for row in lines)
    decisive = outcome_counts["PASSED"] + outcome_counts["FAILED"]
    credits, without_credits = 0, 0
    for run in runs:
        value = run.get("credits_used")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            credits += value
        else:
            without_credits += 1
    without_credits += sum(not index[e.get("test_id")] for e in inputs)
    summary = {
        "overview": {
            "planned": len(inputs),
            "by_outcome": {outcome: outcome_counts[outcome] for outcome in OUTCOMES},
            "decisive_pass_rate": outcome_counts["PASSED"] / decisive if decisive else None,
            "decisive_coverage": decisive / len(inputs) if inputs else None,
            "reported_credits": credits,
            "total_without_credits": without_credits,
            "alerts": _alerts(data, runs, set(counts), counts),
        },
        "cases": lines,
    }
    _save_json(folder / "full-result.json", data)
    _save_json(folder / "summary.json", summary)
    with (folder / "summary.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        for row in lines:
            writer.writerow({**row, "nodes_seen": json.dumps(row["nodes_seen"], ensure_ascii=False)})
    for entry, row in zip(inputs, lines):
        destination = folder / "cases" / entry["case"]["id"]
        matched = index[entry.get("test_id")]
        _save_json(destination / "summary.json", row)
        _save_json(destination / "full-result.json", {
            "invocation_id": data.get("id"), "test_id": entry.get("test_id"), "test_runs": matched,
        })
        (destination / "conversation.txt").write_text(_conversation(entry, matched), encoding="utf-8")
    return summary
