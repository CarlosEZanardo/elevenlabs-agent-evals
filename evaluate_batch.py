"""Text evaluation suite. Preview by default; execution requires --execute.

Keep the single-case evaluate.py example and its reports separate. The SDK
registers definitions and submits selected cases in ONE run_tests request.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.conversational_ai.tests.types.tests_create_request_body import TestsCreateRequestBody_Simulation

from evaluate import OPTIONS, TERMINAL_STATUSES, wait_for_result, read_json, to_dict, save_json
from batch_reports import generate_reports


BASE = Path(__file__).resolve().parent
REJECTIONS = {400, 401, 402, 403, 404, 422, 429}
CREDIT_REFERENCE = 251  # Credits reported by the single-case run on 2026-10-20.


def signature(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_test(case, response, tool_id):
    """Accept any business JSON object as the controlled tool response."""
    if not isinstance(response, dict):
        raise ValueError(f"{case['id']}: the mock must be a JSON object.")
    # This check belongs to the example catalog, rather than the generic runner contract.
    if response.get("status") == "ok" and "courses" in response:
        if not isinstance(response["courses"], list):
            raise ValueError(f"{case['id']}: courses must be a list.")
        if response.get("total") != len(response["courses"]):
            raise ValueError(f"{case['id']}: total does not match the courses list.")
    return {
        "type": "simulation",
        "name": case["name"],
        "simulation_scenario": case["scenario"],
        "simulation_max_turns": case["max_turns"],
        "success_conditions": case["success_criteria"],
        "tool_mock_config": {
            "mocking_strategy": "selected", "fallback_strategy": "raise_error",
            "mocked_tool_ids": [tool_id],
        },
        "tool_mock_overrides": {tool_id: [{
            "parameter_conditions": [],
            "mock_result": json.dumps(response, ensure_ascii=False),
            "is_error": case["mock"]["is_error"],
        }]},
    }


def load_inputs(base, tool_id, selected_cases=None, limit=None, suite_path=None):
    base = Path(base)
    scenarios_root = (base / "scenarios").resolve()
    suite_path_resolved = Path(suite_path) if suite_path is not None else Path("scenarios/suite-20.json")
    suite_path_resolved = (base / suite_path_resolved).resolve()
    if not suite_path_resolved.is_relative_to(scenarios_root) or suite_path_resolved.suffix.lower() != ".json":
        raise ValueError("The suite must be a .json file inside scenarios.")
    suite = read_json(suite_path_resolved)
    cases = suite.get("cases") if isinstance(suite, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("The suite must contain a nonempty list of cases.")
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                or not re.fullmatch(r"(?:0[1-9]|[1-9][0-9])-[a-z0-9-]+", case["id"])):
            raise ValueError("Invalid scenario ID: use a number from 01 to 99 followed by a hyphen and a name.")
        if not isinstance(case.get("name"), str) or not case["name"].strip():
            raise ValueError("Each suite definition must have a nonempty name.")
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Each suite definition must have a distinct ID.")
    if len({c["name"] for c in cases}) != len(cases):
        raise ValueError("Each suite definition must have a distinct name.")
    # Validate the whole suite before selecting or submitting any case.
    inputs = []
    fixtures_root = (base / "fixtures").resolve()
    for case in cases:
        if kind := case.get("tool_expectation"):
            if kind not in {"required", "optional"}:
                raise ValueError(f"{case['id']}: invalid tool expectation.")
        else:
            raise ValueError(f"{case['id']}: missing tool expectation.")
        if type(case["max_turns"]) is not int or not 1 <= case["max_turns"] <= 50:
            raise ValueError(f"{case['id']}: invalid max_turns.")
        if not case.get("scenario") or not case.get("success_criteria"):
            raise ValueError(f"{case['id']}: scenario and success criteria are required.")
        if not all(isinstance(c, str) and c.strip() for c in case["success_criteria"]):
            raise ValueError(f"{case['id']}: success criteria must be nonempty strings.")
        if type(case["mock"]["is_error"]) is not bool:
            raise ValueError(f"{case['id']}: is_error must be a boolean.")
        path = (fixtures_root / case["mock"]["file"]).resolve()
        if not path.is_relative_to(fixtures_root):
            raise ValueError("The mock file must stay inside fixtures.")
        response = read_json(path)
        payload = build_test(case, response, tool_id)
        inputs.append({"case": case, "response": response, "payload": payload,
                         "signature": signature(payload)})
    if selected_cases is not None:
        tokens = [c.strip() for c in selected_cases.split(",") if c.strip()]
        if not tokens:
            raise ValueError("Provide case numbers separated by commas.")
        # Accept case numbers as 1 or 01 without changing the saved ID.
        tokens = [c.zfill(2) if re.fullmatch(r"[0-9]{1,2}", c) else c for c in tokens]
        selected = [e for e in inputs if e["case"]["id"] in tokens or e["case"]["id"][:2] in tokens]
        known = {e["case"]["id"] for e in inputs} | {e["case"]["id"][:2] for e in inputs}
        if unknown := set(tokens) - known:
            raise ValueError(
                f"Scenarios not found: {', '.join(repr(c) for c in sorted(unknown))}. "
                "Available IDs: " + ", ".join(e["case"]["id"] for e in inputs) + ". "
                "Available numbers: " + ", ".join(sorted({e["case"]["id"][:2] for e in inputs})) + "."
            )
        inputs = selected
    elif limit is not None:
        if not 1 <= limit <= len(cases):
            raise ValueError(f"The limit must be between 1 and {len(cases)} for this suite.")
        inputs = inputs[:limit]
    return suite, inputs


def current_state(base):
    path = base / ".batch-state.json"
    state = read_json(path) if path.exists() else {"registrations": {}}
    # The first case preserves the original payload, so its registration can be reused.
    previous = base / ".state.json"
    if previous.exists():
        for key, test_id in read_json(previous).get("registrations", {}).items():
            state.setdefault("registrations", {}).setdefault(key, test_id)
    return state


def saved_folder(base, name):
    path = (base / name).resolve()
    if not path.is_relative_to((base / "batches").resolve()):
        raise ValueError("The saved batch must be inside the batches folder.")
    return path


def register_tests(client, inputs, state, state_path):
    """Save each returned ID; never retry registration or execution automatically."""
    for entry in inputs:
        key = entry["signature"]
        test_id = state.setdefault("registrations", {}).get(key)
        if not test_id:
            test = client.conversational_ai.tests.create(
                request=TestsCreateRequestBody_Simulation(**entry["payload"]), request_options=OPTIONS
            )
            test_id = test.id
            state["registrations"][key] = test_id
            save_json(state_path, state)
        entry["test_id"] = test_id
    ids = [e["test_id"] for e in inputs]
    if len(ids) != len(set(ids)):
        raise ValueError("Two scenarios reference the same registration; check the suite before submitting.")


def start_batch(client, base, suite, inputs, agent_id, branch_id, label):
    state = current_state(base)
    if state.get("pending"):
        raise ValueError("A batch is pending. Use --query before submitting another one.")
    name = "batch_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:6]
    folder = base / "batches" / name
    state_path = base / ".batch-state.json"
    manifest = {
        "label": label, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "suite_version": suite["version"], "sdk_version": version("elevenlabs"),
        "agent_id": agent_id, "branch_id": branch_id, "repeat_count": 1,
        "cases": [e["case"]["id"] for e in inputs], "phase": "registering",
        "dataset_signature": signature([e["signature"] for e in inputs]),
    }
    save_json(folder / "manifest.json", manifest)
    save_json(folder / "inputs.json", inputs)
    register_tests(client, inputs, state, state_path)
    # Save the complete snapshot, including IDs, BEFORE the POST that starts simulations.
    save_json(folder / "inputs.json", inputs)
    manifest["phase"] = "submission_started"
    save_json(folder / "manifest.json", manifest)
    state["latest_folder"] = str(folder.relative_to(base))
    state["pending"] = {"folder": state["latest_folder"], "invocation_id": None}
    save_json(state_path, state)
    try:
        response = client.conversational_ai.agents.run_tests(
            agent_id=agent_id, branch_id=branch_id,
            tests=[{"test_id": e["test_id"]} for e in inputs], repeat_count=1,
            request_options=OPTIONS,
        )
    except ApiError as exc:
        if exc.status_code in REJECTIONS:
            state["pending"] = None
            manifest["phase"] = "submission_rejected"
            save_json(state_path, state)
            save_json(folder / "manifest.json", manifest)
        raise
    state["pending"]["invocation_id"] = response.id
    manifest.update({"invocation_id": response.id, "phase": "in_progress"})
    save_json(state_path, state)
    save_json(folder / "manifest.json", manifest)
    save_json(folder / "full-result.json", to_dict(response))
    return folder, response


def recover(client, base, identifier):
    state = current_state(base)
    name = (state.get("pending") or {}).get("folder") or state.get("latest_folder")
    if not name:
        raise ValueError("No saved batch is available to query.")
    folder = saved_folder(base, name)
    manifest = read_json(folder / "manifest.json")
    inputs = read_json(folder / "inputs.json")
    invocation_id = manifest.get("invocation_id") if identifier == "latest" else identifier
    if not invocation_id:
        raise ValueError("Check ElevenLabs Tests and use --query RUN_ID for the submission whose response was lost.")
    response = client.conversational_ai.tests.invocations.get(
        test_invocation_id=invocation_id, request_options=OPTIONS
    )
    # Never associate the snapshot with a run from another test or agent.
    expected = {e["test_id"] for e in inputs}
    if any(r.test_id not in expected for r in response.test_runs):
        raise ValueError("The supplied ID includes tests that do not belong to this batch.")
    if response.agent_id and response.agent_id != manifest["agent_id"]:
        raise ValueError("The supplied ID belongs to another agent.")
    manifest["invocation_id"] = response.id
    save_json(folder / "manifest.json", manifest)
    state["pending"] = {"folder": name, "invocation_id": response.id}
    save_json(base / ".batch-state.json", state)
    return folder, response


def finalize(client, base, folder, response):
    print("Run:", response.id)
    data = wait_for_result(client, response)
    inputs = read_json(folder / "inputs.json")
    summary = generate_reports(folder, data, inputs)
    runs = data.get("test_runs", [])
    expected = {e["test_id"] for e in inputs}
    finished = bool(data.get("cancelled")) or (
        len(runs) == len(inputs) and {r.get("test_id") for r in runs} == expected
        and all(r.get("status") in TERMINAL_STATUSES for r in runs)
    )
    manifest = read_json(folder / "manifest.json")
    manifest["phase"] = "completed" if finished else "in_progress"
    save_json(folder / "manifest.json", manifest)
    state = current_state(base)
    state["pending"] = None if finished else {"folder": str(folder.relative_to(base)), "invocation_id": response.id}
    save_json(base / ".batch-state.json", state)
    overview = summary["overview"]
    print("\nOutcomes:", json.dumps(overview["by_outcome"], ensure_ascii=False))
    print("Reported credits:", overview["reported_credits"])
    print("Reports:", folder)
    for alert in overview.get("alerts", []):
        print("Note:", alert)
    if not finished:
        print("Results are pending or incomplete. Use --query; it does not start another batch.")
    return 0 if summary["cases"] and all(c["outcome"] == "PASSED" for c in summary["cases"]) else 1


def preview(base, suite, inputs, agent_id, branch_id):
    plan = {
        "kind": "local_preview_without_execution", "suite_version": suite["version"],
        "agent_id": agent_id, "branch_id": branch_id, "count": len(inputs),
        "repeat_count": 1, "credit_reference_per_case": CREDIT_REFERENCE,
        "linear_credit_reference": CREDIT_REFERENCE * len(inputs),
        "cost_note": "Reference from a previous run; this is neither a cost forecast nor a spending cap.",
        "inputs": inputs,
    }
    save_json(base / "batch-plan.json", plan)
    print("LOCAL PREVIEW — no API requests and no simulations started.")
    print("Selected cases:", len(inputs), "| repetitions per case: 1")
    for e in inputs:
        c = e["case"]
        print(f"{c['id']}: {c['name']} | {c['max_turns']} turns | tool {c['tool_expectation']} | {c['mock']['file']} / is_error={c['mock']['is_error']}")
    print("Linear credit reference:", plan["linear_credit_reference"], "(actual usage varies).")
    print("Plan saved to:", base / "batch-plan.json")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--execute", action="store_true", help="Start the selected simulations; consumes resources.")
    mode.add_argument("--query", nargs="?", const="latest", metavar="ID", help="Retrieve the latest batch without starting simulations.")
    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument("--cases", help='Comma-separated numbers or IDs. Example: --cases "01,11,17". Accepts 1 or 01.')
    filter_group.add_argument("--limit", type=int, help="Select the first N cases from the chosen suite.")
    parser.add_argument("--suite", metavar="FILE", help="A .json file inside scenarios. Default: scenarios/suite-20.json.")
    parser.add_argument("--label", default="baseline", help="Label this run for later comparison.")
    args = parser.parse_args(argv)
    load_dotenv(BASE / ".env")
    try:
        if args.query and (args.cases is not None or args.limit is not None or args.suite is not None):
            raise ValueError("--query uses the saved snapshot. Do not combine it with --suite or case filters.")
        key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        agent_id = os.getenv("ELEVENLABS_AGENT_ID", "").strip()
        branch_id = os.getenv("ELEVENLABS_BRANCH_ID", "").strip()
        tool_id = os.getenv("ELEVENLABS_TOOL_ID", "").strip()
        if args.query:
            if not key:
                raise ValueError("Set the key in your local .env file before querying.")
            client = ElevenLabs(api_key=key, timeout=30)
            folder, response = recover(client, BASE, args.query)
            return finalize(client, BASE, folder, response)
        suite, inputs = load_inputs(BASE, tool_id or "tool_example", args.cases, args.limit, args.suite)
        if not args.execute:
            return preview(BASE, suite, inputs, agent_id, branch_id)
        if not all([key, agent_id, branch_id, tool_id]):
            raise ValueError("Set the key and identifiers in your local .env file.")
        print(f"Submitting {len(inputs)} scenarios, one repetition each. This action uses ElevenLabs credits.")
        client = ElevenLabs(api_key=key, timeout=30)
        folder, response = start_batch(client, BASE, suite, inputs, agent_id, branch_id, args.label)
        return finalize(client, BASE, folder, response)
    except ApiError as exc:
        print(f"The API returned HTTP {exc.status_code}. Check the key, permissions, quota and identifiers.")
        print("No automatic retry. If submission is uncertain, check Tests and recover the SAME run.")
        return 2
    except (ValueError, KeyError, OSError) as exc:
        print("Unable to complete:", str(exc))
        return 2
    except Exception as exc:
        print(f"Unable to complete ({type(exc).__name__}). Use --query if a submission has already been attempted.")
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
