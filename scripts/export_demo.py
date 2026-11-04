"""Export local reports as a demonstration without API calls or credentials.

Example (source and destination must be separate folders):
    python scripts/export_demo.py --source LOCAL_PROJECT_PATH --destination .

Read only manifest.json, summary.json, inputs.json and details of cases
listed in each summary. Project known fields; new platform fields are not
published automatically. Omit account metadata, arbitrary tool bodies and
authentication settings.

Platform IDs become deterministic aliases without a reversible mapping file.
Outcomes, usage, criteria and call counts remain unchanged. Redact known email,
URL, path and ID patterns in conversations. The output is a sanitized study
copy rather than a raw API response.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile


NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,159}\Z")
EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.I)
URL = re.compile(r"https?://[^\s<>\"']+", re.I)
WINDOWS_PATH = re.compile(r"(?<!\w)[A-Za-z]:[\\/][^\s<>\"']+")
UNIX_PATH = re.compile(r"/(?:Users|home|tmp|mnt|private|var|opt)/(?:[^\s<>\"']+)")
TOKEN = re.compile(r"\b(?:sk[-_][A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.~+/-]{12,})\b", re.I)
PLATFORM_ID = re.compile(r"\b(?:agent|agtbrch|agtvrsn|suite|test|trun|conv|tool|node|workspace|request|req|call|user|folder)_[A-Za-z0-9_-]{4,}\b")
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
CASE_IDS = ("test_id", "test_run_id", "invocation_id", "agent_id", "branch_id", "version_id")
CASE_TEXTS = ("case_id", "name", "category", "purpose", "signature", "outcome", "platform_status", "platform_evaluation", "evidence", "rationale_text")
OUTCOMES = ("PASSED", "FAILED", "REVIEW_EVIDENCE", "INCONCLUSIVE", "CANCELLED")
TRANSLATION_FIELDS = ("source_language", "content_language", "translation_note")


def alias_id(value):
    """Use the same alias for the same identity across files and batches."""
    if not isinstance(value, str) or not value:
        return None
    return "demo_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def text(value):
    if not isinstance(value, str):
        return None
    value = EMAIL.sub("[email removed]", value)
    value = URL.sub("[URL removed]", value)
    value = WINDOWS_PATH.sub("[local path removed]", value)
    value = UNIX_PATH.sub("[local path removed]", value)
    value = TOKEN.sub("[credential removed]", value)
    value = PLATFORM_ID.sub(lambda m: alias_id(m.group()), value)
    return UUID.sub(lambda m: alias_id(m.group()), value)


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def boolean(value):
    return value if isinstance(value, bool) else None


def strings(value):
    return [text(v) for v in value if isinstance(v, str)] if isinstance(value, list) else []


def safe_name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError("Invalid folder identifier.")
    return value


def read_json(root, path, kind):
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError("A reference points outside the source folder.")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, kind):
        raise ValueError("Unsupported report format.")
    return data


def project_case(case):
    output = {field: text(case.get(field)) for field in CASE_TEXTS}
    output.update({field: alias_id(case.get(field)) for field in CASE_IDS})
    output.update({field: boolean(case.get(field)) for field in ("tool_called", "mock_confirmed", "ran_against_draft")})
    output["credits_used"] = number(case.get("credits_used"))
    output["nodes_seen"] = [alias_id(v) for v in case.get("nodes_seen", []) if isinstance(v, str)]
    return output


def project_summary(summary):
    overview = summary.get("overview", {})
    return {
        "overview": {
            **{k: number(overview.get(k)) for k in ("planned", "decisive_pass_rate", "decisive_coverage", "reported_credits", "total_without_credits")},
            "by_outcome": {k: number(overview.get("by_outcome", {}).get(k)) for k in OUTCOMES},
            "alerts": strings(overview.get("alerts")),
        },
        "cases": [project_case(c) for c in summary.get("cases", []) if isinstance(c, dict)],
    }


def project_manifest(manifest):
    output = {k: text(manifest.get(k)) for k in ("label", "created_at_utc", "suite_version", "sdk_version", "phase", "dataset_signature")}
    output.update({k: alias_id(manifest.get(k)) for k in ("agent_id", "branch_id", "invocation_id")})
    output["repeat_count"] = number(manifest.get("repeat_count"))
    output["cases"] = strings(manifest.get("cases"))
    output["publication"] = "Sanitized demonstration; identifiers replaced and private metadata omitted."
    output.update({key: text(manifest[key]) for key in TRANSLATION_FIELDS
                   if isinstance(manifest.get(key), str)})
    return output


def project_catalog(response):
    output = {k: text(response.get(k)) for k in ("status", "queried_at", "message", "error") if k in response}
    if "total" in response:
        output["total"] = number(response.get("total"))
    courses = []
    for course in response.get("courses", []):
        if not isinstance(course, dict):
            continue
        item = {k: text(course.get(k)) for k in ("course_id", "name", "language", "level", "format", "days", "schedule")}
        item.update({k: number(course.get(k)) for k in ("monthly_fee_brl", "duration_months")})
        item["active"] = boolean(course.get("active"))
        courses.append(item)
    if "courses" in response:
        output["courses"] = courses
    return output


def project_inputs(inputs):
    output = []
    for entry in inputs:
        if not isinstance(entry, dict) or not isinstance(entry.get("case"), dict):
            continue
        case = entry["case"]
        item = {k: text(case.get(k)) for k in ("id", "name", "tool", "scenario", "category", "purpose", "source", "tool_expectation")}
        item["max_turns"] = number(case.get("max_turns"))
        item["success_criteria"] = strings(case.get("success_criteria"))
        output.append({"case": item, "response": project_catalog(entry.get("response", {})), "signature": text(entry.get("signature")), "test_id": alias_id(entry.get("test_id"))})
    return output


def project_call(call):
    # Unrestricted parameters can contain private data or authentication.
    # Preserve execution events and counts, but do not publish raw bodies.
    return {
        "request_id": alias_id(call.get("request_id")),
        "tool_id": alias_id(call.get("tool_id")),
        "tool_name": text(call.get("tool_name")),
        "type": text(call.get("type")),
        "tool_has_been_called": boolean(call.get("tool_has_been_called")),
    }


def project_tool_result(response):
    return {
        "request_id": alias_id(response.get("request_id")),
        "tool_name": text(response.get("tool_name")),
        "type": text(response.get("type")),
        **{k: boolean(response.get(k)) for k in ("tool_has_been_called", "is_error", "is_blocked")},
        "tool_latency_secs": number(response.get("tool_latency_secs")),
        "error_type": text(response.get("error_type")),
    }


def project_message(message):
    output = {k: text(message.get(k)) for k in ("role", "message", "producing_llm")}
    output["time_in_call_secs"] = number(message.get("time_in_call_secs"))
    output["interrupted"] = boolean(message.get("interrupted"))
    output["tool_calls"] = [project_call(t) for t in message.get("tool_calls", []) if isinstance(t, dict)]
    output["tool_results"] = [project_tool_result(t) for t in message.get("tool_results", []) if isinstance(t, dict)]
    # Keep generating-model names without unrestricted account metadata.
    usage = message.get("llm_usage") or {}
    names = set(usage.get("model_usage", {})) if isinstance(usage.get("model_usage"), dict) else set()
    for detail in usage.get("detailed_model_usage", []):
        if isinstance(detail, dict) and isinstance(detail.get("config"), dict):
            name = detail["config"].get("model")
            if isinstance(name, str):
                names.add(name)
    output["llm_usage"] = {"model_usage": {text(name): {} for name in sorted(names)}}
    return output


def project_result(raw):
    runs = []
    for run in raw.get("test_runs", []):
        if not isinstance(run, dict):
            continue
        output = {k: alias_id(run.get(k)) for k in ("test_run_id", "test_invocation_id", "test_id", "agent_id", "branch_id", "version_id")}
        output.update({k: text(run.get(k)) for k in ("status", "test_name")})
        output["ran_against_draft"] = boolean(run.get("ran_against_draft"))
        output["credits_used"] = number(run.get("credits_used"))
        output["agent_responses"] = [project_message(m) for m in run.get("agent_responses", []) if isinstance(m, dict)]
        condition = run.get("condition_result") or {}
        rationale = condition.get("rationale") or {}
        output["condition_result"] = {"result": text(condition.get("result")), "rationale": {"summary": text(rationale.get("summary")), "messages": strings(rationale.get("messages"))}}
        # Preserve relevant numeric charges, omitting tier and unrestricted metadata.
        charging = run.get("charging") or {}
        output["charging"] = {k: number(charging.get(k)) for k in ("call_charge", "llm_charge", "platform_charge", "subagent_charge", "voice_surcharge_charge") if k in charging}
        runs.append(output)
    output = {"invocation_id": alias_id(raw.get("invocation_id")), "test_id": alias_id(raw.get("test_id")), "sanitized": True, "test_runs": runs}
    output.update({key: text(raw[key]) for key in TRANSLATION_FIELDS
                   if isinstance(raw.get(key), str)})
    return output


def call_count(raw):
    """Match dashboard counts, including result-based confirmation and deduplication."""
    total = Counter()
    for run in raw.get("test_runs", []):
        messages = run.get("agent_responses", [])
        confirmed = {(t.get("request_id"), t.get("tool_name")) for m in messages if m.get("role") == "agent" for t in m.get("tool_results", []) if t.get("tool_has_been_called") is True and t.get("is_blocked") is not True and t.get("request_id")}
        seen = set()
        for m in messages:
            if m.get("role") != "agent":
                continue
            for t in m.get("tool_calls", []):
                name, request, flag = t.get("tool_name"), t.get("request_id"), t.get("tool_has_been_called")
                key = (request, name)
                if not name or flag is False or (flag is not True and key not in confirmed):
                    continue
                if request and key in seen:
                    continue
                if request:
                    seen.add(key)
                total[name] += 1
    return total


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError("Source and destination must be separate, non-overlapping folders.")
    root = (source / "batches").resolve()
    if not root.is_relative_to(source) or not root.is_dir():
        raise ValueError("The batches folder is invalid or outside the source project.")
    target = destination / "batches"
    if target.exists() or target.is_symlink():
        raise ValueError("The destination already contains batches. Use a new folder to preserve existing files.")
    destination.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".demo-export-", dir=destination))
    total_batches = total_cases = 0
    try:
        temporary_batches = temporary / "batches"
        temporary_batches.mkdir()
        for folder in sorted(root.iterdir()):
            if not folder.name.startswith("batch_"):
                continue
            safe_name(folder.name)
            if not folder.resolve().is_relative_to(root) or not folder.is_dir():
                raise ValueError("A batch folder points outside the source.")
            manifest = read_json(root, folder / "manifest.json", dict)
            summary = read_json(root, folder / "summary.json", dict)
            inputs = read_json(root, folder / "inputs.json", list)
            exported_summary = project_summary(summary)
            exported_folder = temporary_batches / folder.name
            write_json(exported_folder / "manifest.json", project_manifest(manifest))
            write_json(exported_folder / "summary.json", exported_summary)
            write_json(exported_folder / "inputs.json", project_inputs(inputs))
            for original, exported_case in zip(summary["cases"], exported_summary["cases"], strict=True):
                case_id = safe_name(original["case_id"])
                raw_path = folder / "cases" / case_id / "full-result.json"
                raw = read_json(root, raw_path, dict)
                sanitized = project_result(raw)
                if call_count(raw) != call_count(sanitized):
                    raise ValueError("Sanitization changed the tool counts.")
                case_destination = exported_folder / "cases" / case_id
                write_json(case_destination / "full-result.json", sanitized)
                write_json(case_destination / "summary.json", exported_case)
                conversation = folder / "cases" / case_id / "conversation.txt"
                if not conversation.resolve().is_relative_to(root):
                    raise ValueError("The conversation points outside the source folder.")
                (case_destination / "conversation.txt").write_text(text(conversation.read_text(encoding="utf-8-sig")) or "", encoding="utf-8")
                total_cases += 1
            buffer = io.StringIO(newline="")
            fields = list(exported_summary["cases"][0]) if exported_summary["cases"] else ["case_id", "outcome"]
            writer = csv.DictWriter(buffer, fieldnames=fields)
            writer.writeheader()
            writer.writerows(exported_summary["cases"])
            # csv.Writer already defines line endings. Avoid adding an extra CR
            # on Windows, which would introduce blank lines.
            (exported_folder / "summary.csv").write_text(buffer.getvalue(), encoding="utf-8", newline="")
            total_batches += 1
        if not total_batches:
            raise ValueError("No complete batches found.")
        temporary_batches.rename(target)
    finally:
        # Remove only the temporary folder created inside this destination.
        if temporary.resolve().is_relative_to(destination):
            shutil.rmtree(temporary)
    return {"batches": total_batches, "cases": total_cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Local project containing batches; never reads .env.")
    parser.add_argument("--destination", required=True, type=Path, help="Publishable copy, separate from the source and without an existing batches folder.")
    args = parser.parse_args()
    try:
        outcome = export(args.source, args.destination)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # System errors can contain paths; avoid exposing local values.
        parser.exit(1, f"Export failed ({type(exc).__name__}). Check the source, destination and report format.\n")
    print(f"Export complete: {outcome['batches']} batches, {outcome['cases']} runs. No API calls.")


if __name__ == "__main__":
    main()
