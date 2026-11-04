# A walkthrough of the repository

This guide helps you explore the files before running any program.

## 1. Start with the README

Go to the project's [main page](../README.md). GitHub displays the file list followed by the README: an introduction, links, setup instructions, and the case's limitations.

Look for **Public** and the **main** branch. `main` is the primary version of this project's files. Agent branches in ElevenLabs belong to a separate version-control system.

## 2. Read the test scenarios

Open [SCENARIOS-20.md](../SCENARIOS-20.md) to read the scenarios and criteria as a document. Then open [scenarios/suite-20.json](../scenarios/suite-20.json), which contains the definitions read by the program.

A `.md` file is formatted text; a `.json` file stores structured data. Both explain the same set of cases, but the runner reads the JSON. The [minimal suite](../scenarios/minimal-suite.json) contains cases 01, 11, and 17 as a starting point for adaptation. You can also create other suites.

The current scenario files are in English. The historical results were originally produced in Brazilian Portuguese and translated for readers. Running the English scenarios is a new experiment, with new payload signatures and outcomes.

## 3. Inspect the data supplied to the tool

In [fixtures/](../fixtures/), open the normal catalog, error response, and empty catalog. These files control the selected tool's response during simulations.

For example, a scenario can test whether the agent acknowledges a failed lookup instead of inventing a price. This makes the response predictable without depending on an external API's current availability. It does not automatically isolate other integrations configured on the agent.

## 4. Explore a batch

[batches/](../batches/) contains two reviewed historical examples. Inside each batch:

| File or folder | What it contains |
|---|---|
| `manifest.json` | Date, label, and batch context |
| `inputs.json` | Snapshot of the scenarios and criteria used for that batch |
| `summary.json` | Metrics and outcomes for each case |
| `summary.csv` | Results in a table format |
| `cases/` | Each case's conversation, summary, and sanitized result JSON |

Within a case, `conversation.txt` provides readable messages. Despite its name, `full-result.json` is a sanitized projection in this published sample; the original raw account response is not included.

The English translations preserve recorded metrics, original conclusions, and source signatures. A source signature refers to the Portuguese test definition, so it cannot be recomputed from translated text. See [language provenance](METHODOLOGY.md#language-and-historical-provenance).

For a visual view, open the [online demo](https://ponte-idiomas-evals.streamlit.app/). It contains six batches from the study; this repository's local sample contains two.

## 5. Find the programs

| File | Responsibility |
|---|---|
| `evaluate_batch.py` | Organize cases and request simulations |
| `batch_reports.py` | Assemble results and check evidence |
| `evaluate.py` | Original single-case example |
| `check_access.py` | Check authentication and access to the agent |
| `dashboard_data.py` | Load and organize reports |
| `dashboard.py` | Display metrics, charts, filters, and conversations |

Read the [adaptation guide](ADAPTATION.md) before running your own evaluations. Browsing GitHub files or the dashboard does not start simulations.

## 6. Understand checks and history

The [tests/](../tests/) folder checks the program itself: payload construction, result matching, error handling, and sanitization. It uses simulated data and HTTP responses.

The **Actions** tab shows automated checks. [`.github/workflows/tests.yml`](../.github/workflows/tests.yml) installs dependencies and runs program tests when changes are pushed or proposed in a pull request. It does not request the 20 conversations from ElevenLabs.

A **commit** records a change in the files' history. A **push** sends local commits to GitHub. A **pull request** proposes a change for review before it is merged into the main branch.

GitHub does not automatically receive files saved on your computer. Review new reports before uploading them.

## 7. Download a copy or contribute

On the repository's main page, choose **Code → Download ZIP**. Extract the folder and follow the README. If you use Git, cloning creates a local copy with its history.

To suggest an improvement, open an **Issue** describing the scenario, observed behavior, and expected outcome. Include reviewed examples without keys, personal data, or account metadata. To propose code changes, create a fork and open a pull request.

The [LICENSE](../LICENSE) describes how the code can be reused. Adapt the school examples to your business and review the results against your own criteria.
