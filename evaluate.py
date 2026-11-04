"""First Ponte Idiomas evaluation: scenario -> SDK -> outcome.

With no arguments, show a local preview. --execute starts ONE ElevenLabs test.
--query retrieves the latest run without starting another one.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.conversational_ai.tests.types.tests_create_request_body import (
    TestsCreateRequestBody_Simulation,
)


BASE = Path(__file__).resolve().parent
# Never retry POST automatically: a lost response must not trigger another charge.
OPTIONS = {"max_retries": 0, "timeout_in_seconds": 30}
TERMINAL_STATUSES = {"passed", "failed", "cancelled"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(scenario, catalog, tool_id):
    """Build the test definition. The mock uses the tool ID, rather than its name."""
    if not 1 <= scenario["max_turns"] <= 50:
        raise ValueError("max_turns must be between 1 and 50.")
    if catalog.get("status") != "ok" or catalog.get("total") != len(catalog.get("courses", [])):
        raise ValueError("Invalid test catalog.")
    return {
        "type": "simulation",
        "name": scenario["name"],
        "simulation_scenario": scenario["scenario"],
        "simulation_max_turns": scenario["max_turns"],
        "success_conditions": scenario["success_criteria"],
        "tool_mock_config": {
            "mocking_strategy": "selected",
            "fallback_strategy": "raise_error",
            "mocked_tool_ids": [tool_id],
        },
        "tool_mock_overrides": {
            tool_id: [{
                "parameter_conditions": [],
                "mock_result": json.dumps(catalog, ensure_ascii=False),
                "is_error": False,
            }]
        },
    }


def to_dict(model):
    return model.model_dump(mode="json", exclude_none=True)


def start(client, agent_id, branch_id, payload, state_path, inputs):
    """Reuse an unchanged scenario/mock registration and start one run."""
    state = read_json(state_path) if state_path.exists() else {}
    # After an interruption, query the previous run before attempting another submission.
    if state.get("waiting"):
        raise ValueError("A run is pending. Use --query before starting another one.")
    signature = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    registration_id = state.get("registrations", {}).get(signature)
    if not registration_id:
        test = client.conversational_ai.tests.create(
            request=TestsCreateRequestBody_Simulation(**payload), request_options=OPTIONS
        )
        registration_id = test.id
        state.setdefault("registrations", {})[signature] = registration_id
        save_json(state_path, state)
        print("Test registered:", registration_id)
    else:
        print("Reusing registered test:", registration_id)

    # Save the submission marker before POST. A lost response does not trigger a retry.
    state["waiting"] = True
    state["latest_run"] = None
    state["last_test_id"] = registration_id
    state["inputs"] = inputs
    save_json(state_path, state)
    try:
        response = client.conversational_ai.agents.run_tests(
            agent_id=agent_id,
            branch_id=branch_id,
            tests=[{"test_id": registration_id}],
            repeat_count=1,
            request_options=OPTIONS,
        )
    except ApiError as exc:
        # Definitive rejections did not start a test. Network/5xx errors are uncertain:
        # keep the block until the run history has been checked on the platform.
        if exc.status_code in (400, 401, 402, 403, 404, 422, 429):
            state["waiting"] = False
            save_json(state_path, state)
        raise
    state["latest_run"] = response.id
    save_json(state_path, state)
    return response


def wait_for_result(client, response, seconds=180, interval=3):
    """Polling the outcome does not start additional simulations."""
    limit = time.monotonic() + seconds
    while True:
        data = to_dict(response)
        runs = data.get("test_runs", [])
        if data.get("cancelled") or (runs and all(r.get("status") in TERMINAL_STATUSES for r in runs)):
            return data
        if time.monotonic() >= limit:
            return data  # A pending run stays pending; a timeout never turns it into a pass.
        time.sleep(interval)
        response = client.conversational_ai.tests.invocations.get(
            test_invocation_id=response.id, request_options=OPTIONS
        )


def summarize(data, scenario, catalog):
    """Separate LLM grading from deterministic evidence of the mocked tool response."""
    runs = data.get("test_runs", [])
    if len(runs) != 1:
        return {"outcome": "INCONCLUSIVE", "reason": "Exactly one run was expected."}
    run = runs[0]
    condition = run.get("condition_result") or {}
    rationale = condition.get("rationale") or {}
    reason = " | ".join(filter(None, [rationale.get("summary"), *(rationale.get("messages") or [])]))
    messages = run.get("agent_responses") or []
    calls = [t for m in messages for t in (m.get("tool_calls") or [])]
    tool_results = [t for m in messages for t in (m.get("tool_results") or [])]
    call = any(t.get("tool_name") == scenario["tool"] for t in calls)
    mock_confirmed = False
    for t in tool_results:
        if t.get("tool_name") != scenario["tool"] or t.get("is_error"):
            continue
        try:
            mock_confirmed |= json.loads(t.get("result_value", "")) == catalog
        except (ValueError, TypeError):
            pass

    status, grade = run.get("status"), condition.get("result")
    if status == "passed" and grade == "success":
        outcome = "PASSED" if call and mock_confirmed else "REVIEW_EVIDENCE"
    elif status == "failed" and grade == "failure":
        outcome = "FAILED"
    elif status == "cancelled" or data.get("cancelled"):
        outcome = "CANCELLED"
    else:
        outcome = "INCONCLUSIVE"
    return {
        "scenario": scenario["id"],
        "outcome": outcome,
        "platform_status": status,
        "platform_evaluation": grade or "not reported",
        "tool_called": call,
        "mock_confirmed": mock_confirmed,
        "reason": reason or "No rationale available; inspect the full result.",
        "invocation_id": data["id"],
        "test_id": run.get("test_id"),
        "agent_id": run.get("agent_id") or data.get("agent_id"),
        "branch_id": run.get("branch_id") or data.get("branch_id"),
        "version_id": run.get("version_id") or data.get("version_id") or "not reported",
        "ran_against_draft": run.get("ran_against_draft", data.get("ran_against_draft")),
        "credits_used": run.get("credits_used", "not reported"),
    }


def record(base, data, scenario, catalog, payload):
    """Save inputs, full response, CSV and readable transcript without the API key."""
    folder = base / "results" / data["id"]
    summary = summarize(data, scenario, catalog)
    save_json(folder / "inputs.json", {"scenario": scenario, "catalog": catalog, "test_definition": payload})
    save_json(folder / "full-result.json", data)
    save_json(folder / "summary.json", summary)
    with (folder / "summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary), delimiter=";")
        writer.writeheader()
        writer.writerow(summary)
    lines = ["Ponte Idiomas — text evaluation", f"Run: {data['id']}", ""]
    for run in data.get("test_runs", []):
        for m in run.get("agent_responses") or []:
            if m.get("message"):
                lines.append(f"{m.get('role', '?')}: {m['message']}")
            for t in m.get("tool_calls") or []:
                lines.append(f"  [call: {t.get('tool_name', '?')}]")
            for t in m.get("tool_results") or []:
                lines.append(f"  [response: {t.get('tool_name', '?')}; error={t.get('is_error')}]")
    (folder / "conversation.txt").write_text("\n".join(lines), encoding="utf-8")
    return summary, folder


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--preview", action="store_true", help="Local preview without API calls (default).")
    action.add_argument("--execute", action="store_true", help="Register/reuse the test and start ONE simulation.")
    action.add_argument("--query", nargs="?", const="latest", metavar="ID", help="Query the latest run or the given ID without starting another run.")
    args = parser.parse_args(argv)
    load_dotenv(BASE / ".env")
    scenario = read_json(BASE / "scenarios" / "01-english-course-info.json")
    catalog = read_json(BASE / "fixtures" / "catalog.json")
    tool_id = os.getenv("ELEVENLABS_TOOL_ID", "")
    payload = prepare(scenario, catalog, tool_id or "tool_example")

    if not (args.execute or args.query):
        print("LOCAL PREVIEW — no API calls; no simulations started.\n")
        print("Scenario:", scenario["name"])
        print("Maximum turns:", scenario["max_turns"])
        print("Tool with a fixed response:", scenario["tool"])
        for i, criterion in enumerate(scenario["success_criteria"], 1):
            print(f"Criterion {i}: {criterion}")
        print("\nAdditional local checks: tool called and response matches the fixed catalog.")
        print("Next: configure .env and use --execute (consumes ElevenLabs resources).")
        return 0

    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    agent_id = os.getenv("ELEVENLABS_AGENT_ID", "").strip()
    branch_id = os.getenv("ELEVENLABS_BRANCH_ID", "").strip()
    if not key or not agent_id or not branch_id or not tool_id:
        print("Set ELEVENLABS_API_KEY and the identifiers in your local .env file. Keep the key out of chat.")
        return 2
    state_path = BASE / ".state.json"
    # The SDK keeps the key in memory; reports and terminal output do not include it.
    client = ElevenLabs(api_key=key, timeout=30)
    try:
        if args.execute:
            print("Starting ONE text simulation, up to five turns, against the configured agent and branch.")
            response = start(client, agent_id, branch_id, payload, state_path, {
                "scenario": scenario, "catalog": catalog, "test_definition": payload,
            })
            # Keep this run's inputs so that --query uses the same definitions,
            # even if the user later changes the scenario or catalog.
            save_json(BASE / "results" / response.id / "inputs.json", {
                "scenario": scenario, "catalog": catalog, "test_definition": payload,
            })
        else:
            state = read_json(state_path) if state_path.exists() else {}
            identifier = state.get("latest_run") if args.query == "latest" else args.query
            if not identifier:
                print("No saved run ID. If a previous submission failed, check ElevenLabs Tests before retrying.")
                return 2
            inputs = state.get("inputs")
            if not inputs:
                print("No saved inputs are available to recover this run.")
                return 2
            scenario, catalog, payload = inputs["scenario"], inputs["catalog"], inputs["test_definition"]
            response = client.conversational_ai.tests.invocations.get(
                test_invocation_id=identifier, request_options=OPTIONS
            )
            if any(r.test_id != state.get("last_test_id") for r in response.test_runs):
                print("This ID belongs to another test. Use the run ID submitted by this project.")
                return 2
            state["latest_run"] = response.id
            save_json(state_path, state)
        print("Run:", response.id)
        data = wait_for_result(client, response)
        summary, folder = record(BASE, data, scenario, catalog, payload)
        runs = data.get("test_runs", [])
        finished = data.get("cancelled") or (runs and all(r.get("status") in TERMINAL_STATUSES for r in runs))
        state = read_json(state_path)
        state["waiting"] = not bool(finished)
        save_json(state_path, state)
        print("\nOutcome:", summary["outcome"])
        print("Rationale:", summary.get("reason", ""))
        print("Tool called:", summary.get("tool_called", False))
        print("Fixed catalog confirmed:", summary.get("mock_confirmed", False))
        print("Reports:", folder)
        if not finished:
            print("Still pending. Use --query; it does not start another simulation.")
        return 0 if summary["outcome"] == "PASSED" else 1
    except ApiError as exc:
        # Do not print error headers or bodies, which may contain account information.
        print(f"The API returned HTTP {exc.status_code}. Check the key, permissions and IDs.")
        if exc.status_code in (401, 403):
            print("The key must allow agent access, test creation and test execution.")
        print("No automatic retry was attempted. Check Tests before repeating an uncertain submission.")
        return 2
    except ValueError as exc:
        print(str(exc))
        return 2
    except Exception as exc:
        print(f"Unable to complete ({type(exc).__name__}). No automatic retry was attempted.")
        print("Use --query if a run ID is available. Otherwise, check ElevenLabs Tests.")
        return 2


if __name__ == "__main__":
    # Use UTF-8 output on supported Windows terminals.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
