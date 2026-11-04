# Evaluate your own agent

This guide assumes that you already have an ElevenLabs agent. It explains how to reuse the runner and adapt the examples. The repository does not create the agent, its prompts, or its knowledge base.

The current scenarios are written in English. The included historical reports are English translations of runs originally conducted in Brazilian Portuguese. Running the current scenarios against your own agent is a new experiment; the historical pass rate does not predict its outcome.

## 1. Set up the local environment

Use Python 3.12 and open a terminal in the project folder.

Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-evals.txt
Copy-Item .env.example .env
```

Linux or macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-evals.txt
cp .env.example .env
```

To run the dashboard and all program tests, also install `requirements.txt` in the same environment. If you already created an environment while exploring the dashboard, keep using it and install the additional dependencies.

## 2. Configure your account and agent

Fill in your local `.env`:

| Variable | Expected value |
|---|---|
| `ELEVENLABS_API_KEY` | Your API key, with access to agent testing and the selected agent |
| `ELEVENLABS_AGENT_ID` | Your agent ID |
| `ELEVENLABS_BRANCH_ID` | The ID of the agent branch to evaluate |
| `ELEVENLABS_TOOL_ID` | The ID of the tool whose response the test will control |

Use identifiers from your own configuration. The `demo_...` aliases in published reports cannot query or run the original agent.

Keep `.env` local; it is covered by `.gitignore`. Do not place the key in scenarios, source code, or a hosted dashboard. Exploring the sample dashboard does not require this file.

To check authentication before starting simulations:

```powershell
.\.venv\Scripts\python.exe check_access.py
```

This checks access to the agent without starting evaluations. An ElevenLabs agent branch is separate from the GitHub repository's `main` branch.

## 3. Match the tool contract

The example uses a tool named `list_courses`, with responses such as `fixtures/catalog.json`. A mock is linked by **tool ID**; the evidence checker looks for the tool **name** specified in each scenario.

The runner accepts any JSON object as a controlled response. For the example catalog:

- `status` is `ok` or `error`.
- When `status=ok` and `courses` is present, the runner checks that `total` matches the number of courses.
- Each scenario supplies one response for the selected tool.

Course fields such as price, level, format, and schedule are specific to this example. For another business, adapt the fixtures, criteria, and tool expectations. You can add contract checks to `build_test` in `evaluate_batch.py`; also review the evidence checks in `batch_reports.py`.

If your agent uses an equivalent tool, put its actual name in the scenarios' `tool` field and its ID in `.env`. Supporting multiple tools or responses conditional on arguments requires extending the runner's mock mapping.

The selected mock controls that tool's response during the simulation. It does not test the availability of a real external API. Review the agent's other integrations separately: the example does not automatically isolate every external tool.

## 4. Adapt the scenarios and criteria

Start with `scenarios/minimal-suite.json`, containing cases 01, 11, and 17. To explore the larger suite, read `SCENARIOS-20.md` and `scenarios/suite-20.json`.

| Scenario field | What to define |
|---|---|
| `id` and `name` | Unique scenario identifiers and names |
| `scenario` | The simulated customer's goal and behavior |
| `success_criteria` | Observable outcomes for the grader to assess |
| `max_turns` | Maximum simulation turns |
| `tool` | Tool name to look for in the evidence |
| `tool_expectation` | `required` or `optional` |
| `source` | Where the expected facts or rules come from |
| `mock.file` | Controlled response file within `fixtures/` |
| `mock.is_error` | Whether to mark the response as a tool error |

Create a suite with the cases you need and save it under `scenarios/`. Select it with `--suite scenarios/YOUR-FILE.json`. The default is `scenarios/suite-20.json`. IDs and names must be unique. To select part of a suite, add `--cases "01,11"`, or use `--limit 2` to select its first two cases.

IDs follow the format `01-scenario-name`, with a prefix from 01 to 99. The accepted turn limit is 1 to 50. Write criteria that can be checked: give the correct price, acknowledge missing information, or clarify a learner's profile before recommending a course.

The administrative scenarios assume that the agent has compatible school policies in its knowledge base or prompts. Supply those rules yourself or rewrite the cases. The original integration and institutional PDF are not included. Keep an English-speaking agent for the current instructions, or adapt the scenario, criteria, and expected responses to your chosen language.

The single-case example `evaluate.py` reads `scenarios/01-english-course-info.json`. If you use it after adapting the suite, keep that definition and its catalog consistent with case 01.

## 5. Preview without API requests

```powershell
.\.venv\Scripts\python.exe evaluate_batch.py --preview --suite scenarios/minimal-suite.json
```

The preview displays the selection and writes a local `batch-plan.json`. It does not start simulations or instantiate the ElevenLabs client. It works without a key, so you can inspect the plan before configuring credentials and executing it.

To filter a suite, use `--cases "01,11"`. Keep the list in quotes in PowerShell. Numbers with or without a leading zero are accepted: `1` and `01` select the same case.

## 6. Run a small selection and review it

This requests a new batch in your account and **may consume ElevenLabs credits**:

```powershell
.\.venv\Scripts\python.exe evaluate_batch.py --execute --suite scenarios/minimal-suite.json --label first-calibration
```

Run only cases you have adapted. The runner registers or reuses test definitions and requests a run for each selected case. It does not edit the agent's prompt, workflow, or publication settings.

After execution, check:

1. Whether the conversation meets the criteria and uses the expected data.
2. Whether the grader's explanation supports its pass or fail conclusion.
3. Whether the required tool call and response are evidenced.
4. Whether agent version, turns, and consumption support a fair comparison.

Read some passed cases too. The historical study contains a false positive identified through human review.

## 7. Query a pending run before repeating it

```powershell
.\.venv\Scripts\python.exe evaluate_batch.py --query
```

This retrieves the last saved batch without starting another. Do not combine `--query` with `--suite` or case filters: querying uses the saved input snapshot. If a submission has an uncertain outcome, inspect it on the platform and recover the same run ID. Do not delete local state to bypass an unresolved submission. Repeating `--execute` starts another batch and may incur additional consumption.

`--label` identifies the batch locally. A signature identifies the prepared test definition; the version returned by the platform identifies the agent actually evaluated. Historical source signatures belong to the original Portuguese definitions, so they do not match newly prepared English payloads.

## 8. Explore results and compare changes

Each batch creates a folder in `batches/` with a manifest, input snapshot, JSON and CSV summaries, and case details. With dashboard dependencies installed:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

To compare an agent before and after a change, keep scenarios and mocks the same, record the change, and run another batch with a new label. Check both improvements and regressions. Changing the test creates a different definition; changing its language does too.

On Linux or macOS, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` in these commands.

## Share results after review

New local batches are ignored by Git because they may contain account metadata and conversation data. A hosted dashboard does not automatically receive files from your computer.

To prepare a shareable sample:

```powershell
.\.venv\Scripts\python.exe scripts/export_demo.py --source PATH_TO_LOCAL_PROJECT --destination NEW_EXPORT_FOLDER
```

Source and destination must be separate folders, and the destination must not already contain a `batches/` folder. The exporter projects known fields, substitutes IDs, and removes recognized patterns for email addresses, URLs, paths, and credentials. Review the output before publication: names, phone numbers, or secrets in other formats may need additional removal. Exporting does not translate new conversations.

To check the program without real API requests, install both dependency files and run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
