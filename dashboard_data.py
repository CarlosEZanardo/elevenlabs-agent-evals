"""Read local dashboard reports without network access or mutations.

Public interface:
    discover_batches(base) -> (batches, warnings)
        ``base`` is the project folder or its ``batches`` folder. Each batch
        contains manifest metadata, an ``overview`` and copied rows from
        ``summary.json``. Missing measurements remain ``None`` rather than
        becoming zero or a pass. Discovery does not open full-result files.

    read_detail(base, batch_id, case_id) -> dict
        Read only a case authorized by the summary, its input snapshot and
        full result. ``messages`` preserves events from every role. ``models``
        comes only from agent events, never aggregate evaluator or simulated
        customer usage. Tool counts use executed top-level events without
        counting nested workflow tools again.

Original files and automated outcomes are preserved. No human-review grade
is inferred. Read errors are collected in ``warnings``; in a detail result,
``warning`` aliases the same list for existing consumers.
"""

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re


OUTCOMES = ("PASSED", "FAILED", "REVIEW_EVIDENCE", "INCONCLUSIVE", "CANCELLED")
LOCAL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,159}\Z")
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
}
CASE_FIELDS = (
    "case_id", "name", "category", "purpose", "signature", "outcome",
    "platform_status", "platform_evaluation", "evidence", "tool_called",
    "mock_confirmed", "rationale_text", "test_id", "test_run_id", "invocation_id",
    "agent_id", "branch_id", "version_id", "ran_against_draft", "credits_used", "nodes_seen",
)


def _safe_name(value):
    return (isinstance(value, str) and bool(LOCAL_NAME.fullmatch(value))
            and value.upper() not in WINDOWS_RESERVED)


def _within(root, path):
    """Resolve paths before reading to block symlinks outside the root."""
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("The path points outside the batches folder.")
    return resolved


def _root(base):
    project = Path(base).resolve()
    if project.name == "batches":
        return project
    # Do not follow a batches-folder link outside the project.
    return _within(project, project / "batches")


def _json(root, path, kind, warnings, context):
    try:
        safe = _within(root, path)
        value = json.loads(safe.read_text(encoding="utf-8-sig"))
        if not isinstance(value, kind):
            warnings.append(f"{context}: unexpected format in {path.name}.")
            return None
        return value
    except FileNotFoundError:
        warnings.append(f"{context}: missing file {path.name}.")
    except (OSError, UnicodeError, ValueError, RuntimeError):
        warnings.append(f"{context}: could not safely read {path.name}; "
                      "the file may be incomplete, invalid or outside the allowed folder.")
    return None


def _text(root, path, warnings, context):
    try:
        return _within(root, path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        warnings.append(f"{context}: missing file {path.name}.")
    except (OSError, UnicodeError, ValueError, RuntimeError):
        warnings.append(f"{context}: could not safely read {path.name}.")
    return ""


def _number(value, integer=False, rate=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        if not math.isfinite(value) or value < 0:
            return None
    except (ValueError, OverflowError):
        return None
    if integer and (not isinstance(value, int)):
        return None
    if rate and value > 1:
        return None
    return value


def _string(value):
    return value if isinstance(value, str) and value.strip() else None


def _string_list(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _dict_list(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _overview(summary, warnings, context):
    original = summary.get("overview")
    if not isinstance(original, dict):
        warnings.append(f"{context}: missing or invalid overview; metrics are unknown.")
        original = {}
    overview = deepcopy(original)
    counts = original.get("by_outcome")
    counts = counts if isinstance(counts, dict) else {}
    overview["by_outcome"] = {
        key: _number(counts.get(key), integer=True) for key in OUTCOMES
    }
    for field in ("planned", "total_without_credits"):
        overview[field] = _number(original.get(field), integer=True)
    for field in ("decisive_pass_rate", "decisive_coverage"):
        overview[field] = _number(original.get(field), rate=True)
    overview["reported_credits"] = _number(original.get("reported_credits"))
    overview["alerts"] = _string_list(original.get("alerts"))
    if any(overview.get(field) is None for field in (
            "planned", "decisive_pass_rate", "decisive_coverage",
            "reported_credits", "total_without_credits")):
        warnings.append(f"{context}: some metrics are missing or unmeasured and are shown as unknown.")
    return overview


def _cases(summary, warnings, context):
    rows = summary.get("cases")
    if not isinstance(rows, list):
        warnings.append(f"{context}: missing or invalid case list.")
        return []
    counts = Counter(row["case_id"].casefold() for row in rows
                        if isinstance(row, dict) and _safe_name(row.get("case_id")))
    cases = []
    duplicates = set()
    for row in rows:
        if not isinstance(row, dict) or not _safe_name(row.get("case_id")):
            warnings.append(f"{context}: an invalid case row was ignored.")
            continue
        identifier = row["case_id"]
        if counts[identifier.casefold()] != 1:
            if identifier.casefold() not in duplicates:
                warnings.append(f"{context}: duplicate case {identifier}; ambiguous association omitted.")
                duplicates.add(identifier.casefold())
            continue
        case = {field: None for field in CASE_FIELDS}
        case.update(deepcopy(row))
        for field in CASE_FIELDS:
            if field not in ("tool_called", "mock_confirmed", "ran_against_draft", "credits_used", "nodes_seen"):
                case[field] = _string(row.get(field))
        case["credits_used"] = _number(row.get("credits_used"))
        for field in ("tool_called", "mock_confirmed", "ran_against_draft"):
            case[field] = row.get(field) if isinstance(row.get(field), bool) else None
        case["nodes_seen"] = _string_list(row.get("nodes_seen"))
        if case["outcome"] not in OUTCOMES:
            case["outcome"] = None
            warnings.append(f"{context}: missing or unknown outcome for {identifier}.")
        cases.append(case)
    return cases


def _order(batch):
    timestamp = batch.get("created_at_utc")
    try:
        instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        return instant.timestamp(), batch["batch_id"]
    except (AttributeError, TypeError, ValueError, OSError, OverflowError):
        pass
    try:
        instant = datetime.strptime(batch["batch_id"][6:22], "%Y%m%dT%H%M%SZ")
        return instant.replace(tzinfo=timezone.utc).timestamp(), batch["batch_id"]
    except (TypeError, ValueError, OSError, OverflowError):
        return float("-inf"), batch["batch_id"]


def discover_batches(base: Path) -> tuple[list[dict], list[str]]:
    """Discover newest batches first, reading only manifests and summaries.

    ``draft=True`` means at least one case ran against a draft.
    ``False`` requires every known case to be explicitly False;
    ``None`` means evidence is insufficient. Mixed states produce a warning.
    """
    warnings, batches = [], []
    try:
        root = _root(base)
        folders = list(root.iterdir())
    except (OSError, ValueError, RuntimeError):
        return [], ["The batches folder is unavailable or unsafe to read."]
    for folder in folders:
        if not folder.name.startswith("batch_"):
            continue
        context = folder.name
        try:
            if not _safe_name(folder.name):
                raise ValueError("Invalid batch name.")
            safe = _within(root, folder)
            if not safe.is_dir():
                continue
        except (OSError, ValueError, RuntimeError):
            warnings.append(f"{context}: unsafe or inaccessible folder; batch ignored.")
            continue
        manifest = _json(root, folder / "manifest.json", dict, warnings, context) or {}
        summary = _json(root, folder / "summary.json", dict, warnings, context) or {}
        cases = _cases(summary, warnings, context)
        label = _string(manifest.get("label"))
        timestamp = _string(manifest.get("created_at_utc"))
        for case in cases:
            case.update(batch_id=folder.name, batch_label=label, batch_created_at_utc=timestamp)
        states = [c.get("ran_against_draft") for c in cases]
        draft = True if True in states else (
            False if states and all(state is False for state in states) else None)
        if True in states and False in states:
            warnings.append(f"{context}: the batch contains both draft and published results.")
        batch = {
            "batch_id": folder.name, "folder": str(safe),
            "label": label, "created_at_utc": timestamp,
            "suite_version": _string(manifest.get("suite_version")),
            "dataset_signature": _string(manifest.get("dataset_signature")),
            "invocation_id": _string(manifest.get("invocation_id")),
            "phase": _string(manifest.get("phase")),
            "agent_id": _string(manifest.get("agent_id")),
            "branch_id": _string(manifest.get("branch_id")),
            "source_language": _string(manifest.get("source_language")),
            "content_language": _string(manifest.get("content_language")),
            "translation_note": _string(manifest.get("translation_note")),
            "overview": _overview(summary, warnings, context), "cases": cases,
            "versions": sorted({c["version_id"] for c in cases if _string(c.get("version_id"))}),
            "draft": draft,
        }
        batches.append(batch)
    batches.sort(key=_order, reverse=True)
    return batches, warnings


def _run(raw, case, warnings):
    runs = raw.get("test_runs")
    if not isinstance(runs, list):
        warnings.append("The full result has no valid run list.")
        return None
    runs = [run for run in runs if isinstance(run, dict)]
    run_id = case.get("test_run_id")
    if run_id:
        candidates = [run for run in runs if run.get("test_run_id") == run_id]
    elif case.get("test_id"):
        candidates = [run for run in runs if run.get("test_id") == case["test_id"]]
    else:
        candidates = runs
    if len(candidates) != 1:
        warnings.append("Could not associate a unique run with the case; messages omitted.")
        return None
    return candidates[0]


def _models(messages):
    models = set()
    for message in messages:
        if message.get("role") != "agent":
            continue
        if _string(message.get("producing_llm")):
            models.add(message["producing_llm"])
        usage = message.get("llm_usage")
        if not isinstance(usage, dict):
            continue
        by_model = usage.get("model_usage")
        if isinstance(by_model, dict):
            models.update(name for name in by_model if _string(name))
        details = usage.get("detailed_model_usage")
        if isinstance(details, list):
            for detail in details:
                config = detail.get("config") if isinstance(detail, dict) else None
                if isinstance(config, dict) and _string(config.get("model")):
                    models.add(config["model"])
    return sorted(models)


def _count_tools(messages, warnings):
    # Results only confirm older calls without an explicit execution flag;
    # they are not counted again, and nested_tools are not traversed.
    confirmed = {
        (t.get("request_id"), t.get("tool_name"))
        for message in messages if message.get("role") == "agent"
        for t in _dict_list(message.get("tool_results"))
        if t.get("tool_has_been_called") is True
        and t.get("is_blocked") is not True and _string(t.get("request_id"))
    }
    counts, seen, unconfirmed = Counter(), set(), 0
    for message in messages:
        if message.get("role") != "agent":
            continue
        calls = message.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict) or not _string(call.get("tool_name")):
                continue
            name = call["tool_name"]
            request_id = _string(call.get("request_id"))
            flag = call.get("tool_has_been_called")
            if flag is False:
                continue
            if flag is not True and (request_id, name) not in confirmed:
                unconfirmed += 1
                continue
            key = (request_id, name)
            if request_id and key in seen:
                continue
            if request_id:
                seen.add(key)
            counts[name] += 1
    if unconfirmed:
        warnings.append(f"{unconfirmed} call(s) without execution evidence were excluded from the count.")
    return dict(sorted(counts.items()))


def read_detail(base: Path, batch_id: str, case_id: str) -> dict:
    """Open a saved case without rerunning tests or inferring a human review."""
    warnings = []
    detail = {
        "case": None, "criteria": [], "script": None, "messages": [],
        "conversation": "", "full_result": {}, "models": [],
        "tool_counts": {}, "warnings": warnings, "warning": warnings,
    }
    if (not _safe_name(batch_id) or not batch_id.startswith("batch_")
            or not _safe_name(case_id)):
        warnings.append("Invalid batch or case identifier; no detail was opened.")
        return detail
    try:
        root = _root(base)
        folder = _within(root, root / batch_id)
        case_folder = _within(root, folder / "cases" / case_id)
    except (OSError, ValueError, RuntimeError):
        warnings.append("The detail path is invalid or outside the allowed folder.")
        return detail
    summary = _json(root, folder / "summary.json", dict, warnings, batch_id) or {}
    cases = [c for c in _cases(summary, warnings, batch_id) if c["case_id"] == case_id]
    if len(cases) != 1:
        warnings.append("The case is not uniquely associated with this batch summary.")
        return detail
    detail["case"] = cases[0]
    inputs = _json(root, folder / "inputs.json", list, warnings, batch_id)
    if inputs is not None:
        matches = [e["case"] for e in inputs if isinstance(e, dict)
                           and isinstance(e.get("case"), dict) and e["case"].get("id") == case_id]
        if len(matches) == 1:
            entry = matches[0]
            detail["criteria"] = _string_list(entry.get("success_criteria"))
            detail["script"] = _string(entry.get("scenario"))
        else:
            warnings.append("The snapshot has no unique definition for this case.")
    detail["conversation"] = _text(root, case_folder / "conversation.txt", warnings, case_id)
    raw = _json(root, case_folder / "full-result.json", dict, warnings, case_id)
    if raw is not None:
        detail["full_result"] = raw
        run = _run(raw, detail["case"], warnings)
        if run is not None:
            messages = run.get("agent_responses")
            if isinstance(messages, list):
                detail["messages"] = [m for m in messages if isinstance(m, dict)]
                if len(detail["messages"]) != len(messages):
                    warnings.append("Invalid conversation events were ignored.")
            else:
                warnings.append("The run has no valid message list.")
    detail["models"] = _models(detail["messages"])
    detail["tool_counts"] = _count_tools(detail["messages"], warnings)
    return detail
