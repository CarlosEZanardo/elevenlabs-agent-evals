"""Check authentication by querying the agent without starting evaluations."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError


BASE = Path(__file__).resolve().parent


def main():
    # Use the same configuration source and precedence as the runner.
    load_dotenv(BASE / ".env")
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        print("Set ELEVENLABS_API_KEY in your local .env file and save it.")
        return 2
    agent_id = os.getenv("ELEVENLABS_AGENT_ID", "").strip()
    branch_id = os.getenv("ELEVENLABS_BRANCH_ID", "").strip()
    if not agent_id or not branch_id:
        print("Set ELEVENLABS_AGENT_ID and ELEVENLABS_BRANCH_ID in your local .env file.")
        return 2
    try:
        client = ElevenLabs(api_key=key, timeout=30)
        agent = client.conversational_ai.agents.get(
            agent_id=agent_id, branch_id=branch_id,
            request_options={"max_retries": 0},
        )
    except ApiError as exc:
        guidance = {
            401: "The key was rejected. Check that the replacement is active and saved in .env.",
            403: "Access denied. Check ElevenAgents: Write and any IP restrictions.",
            404: "Agent or branch not found. Check the identifiers and workspace.",
            429: "The API rate-limited the query. Wait before trying again.",
        }
        print(f"HTTP {exc.status_code}: {guidance.get(exc.status_code, 'The query did not complete.')}")
        return 2
    except Exception as exc:
        # Do not display HTTP bodies, headers or credential values.
        print(f"Query failed ({type(exc).__name__}). Check the connection and SDK installation.")
        return 2
    print("Access confirmed: authentication and agent reads are working.")
    print("Agent:", agent.name)
    print("No simulations started; no configuration changed.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
