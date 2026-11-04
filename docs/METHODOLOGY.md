# Method, evidence, and limitations

## The problem studied

The case evaluates a language-school assistant: answering course questions, helping people choose, respecting boundaries, and handling failures. The exercise turns impressions from individual conversations into scenarios and comparable evidence.

Simulations are text-based. They do not measure audio quality, interruptions, voice latency, load, or concurrent service.

## Evaluation cycle

1. Write a simulated customer's instructions, observable criteria, and turn limit.
2. Fix the tool responses to control the available data.
3. Run the selection on the configured agent branch and record the version returned by the platform.
4. Receive ElevenLabs' assessment of the criteria and check tool evidence in Python.
5. Review conversations and explanations, including some passed cases.
6. Change one hypothesis in the agent and repeat the same cases to check improvements and regressions.

The method applies concepts from [Claude Academy's evaluation workflow](https://academy.claude.com/courses/building-with-the-claude-api/a-typical-eval-workflow) using [ElevenLabs Agent Testing](https://elevenlabs.io/docs/eleven-agents/customization/agent-testing). Runs use the ElevenLabs SDK. Codex assisted with development and investigation of the results.

## Language and historical provenance

The historical experiments were conducted in **Brazilian Portuguese**. This repository translates their conversations, scenario descriptions, and explanations into English for readers. These translations are a presentation of existing evidence, not newly executed English-language evaluations.

Recorded metrics, platform conclusions, dates, BRL amounts, and original source signatures are preserved. Translating the presentation does not change what the original agent was tested on or establish how it would perform in English.

Historical signatures refer to the original Portuguese test definitions. A hash computed from the current English scenarios or translated input text will differ. Do not use that difference to infer that the original historical record was rerun or that its test changed during the original batch.

The executable scenario files are now in English. Evaluating them requires an appropriately configured English-speaking agent, or a deliberate adaptation to another language. Those runs produce new payloads and signatures and need their own review; they do not reproduce the historical 20/20 result by translation alone.

## Dataset and controlled responses

The full suite contains 20 scenarios. Cases 01–16 were used for development and 17–20 were reserved for an educational validation exercise. All were prepared within the same project and their content is known; this is not an independent benchmark.

Criteria allow paraphrases and assess correct outcomes rather than requiring exact wording. Visiting a particular workflow node is not itself a success requirement when the user's need has been met. Administrative questions may not require a catalog lookup.

| Mock profile | Response | Expected behavior |
|---|---|---|
| Normal catalog | Three courses with fixed details | Answer or recommend without contradicting the data |
| Empty catalog | Successful response with an empty list | Acknowledge that no active courses were returned |
| Application error | Error JSON with `is_error=false` | Acknowledge that the current data could not be confirmed |
| Tool error | Response marked `is_error=true` | Handle the failure without inventing facts |

An expected tool failure can produce a passed conversation if the agent handles it correctly. The mock replaces the selected catalog tool's response; it does not test the availability of a real spreadsheet or API. System and workflow tools continue operating, and other integrations require their own review. The current example tool is named `list_courses`.

## Signatures, versions, and repetitions

A signature hashes the prepared test definition, including scenario instructions, criteria, and mock response. It allows a registered definition to be reused when unchanged and identifies changes to that definition. It does not describe the agent's entire state.

The runner records the returned agent version and draft information when the platform provides them. When comparing changes to an agent, keep the criteria and mocks fixed and inspect the version actually evaluated.

`--label` identifies a batch locally. Repeating `--execute` creates a new batch and may consume credits. Investigate and query a submission with a lost response before attempting it again.

## Interpreting outcomes

ElevenLabs grades the natural-language criteria. Python checks the tool call and response according to the scenario's expectations. The summary distinguishes:

| Outcome | Meaning |
|---|---|
| `PASSED` | The evaluation passed and required evidence was confirmed |
| `FAILED` | The evaluation reported a failure against the criteria |
| `REVIEW_EVIDENCE` | The evaluation passed but required evidence was not confirmed |
| `INCONCLUSIVE` | Pending or unknown result, or a technical error |
| `CANCELLED` | The run was cancelled |

These are automated classifications. Read the conversation and explanation before concluding that service failed or that the agent is ready for production.

## Dashboard metrics

| Metric | Calculation or source | Interpretation |
|---|---|---|
| Automatic pass rate | Passed ÷ (passed + failed) | Excludes inconclusive, cancelled, and evidence-review cases |
| Decisive coverage | (Passed + failed) ÷ planned cases | Shows how much of the batch reached a decisive outcome |
| Reported credits | Consumption recorded in the results | Does not represent a balance, monetary price, or consumption cap |
| Transition calls | Executed transition-tool events | A high count warrants investigation but does not automatically fail a case |
| Identical definition | Matching test signature | Does not establish identical agent, model, or runtime conditions |

Missing values remain missing rather than becoming zero. Agent models are read from the relevant messages, without attributing simulator or grader models to the agent. Tool counts use executed events and do not count nested workflow return data a second time.

## Sample included in this repository

The full study contains six batches and 51 case runs. The public repository includes two sanitized, translated batches with **22 case runs and 9,451 reported credits**:

| Batch | Included cases | Original automated outcome | Credits |
|---|---|---|---:|
| `triage-v2-override` | 07 and 13 | 07 failed; 13 passed | 776 |
| `full-baseline`, October 29, 2026 at 21:06, São Paulo time | 01–20 | 20 passed | 8,675 |

The batches cover different selections. Pooling their results does not produce a comparable measure of agent improvement. The online demo retains the six-batch study; the local dashboard opens this repository's two-batch sample.

Human review of the full batch found:

- **Case 07:** the agent repeated a question before the user answered, despite a waiting criterion. This was a false positive for that criterion.
- **Case 14:** the final answer was adequate, but the workflow oscillated between two nodes 135 times. There were 137 transition calls including entry and termination, and 3,384 credits—roughly 39% of the batch's consumption.

These observations were not converted into additional grades in the reports. The dashboard retains the original automatic conclusions and notes that structured human assessments are absent from the data. Review the final content, path through the workflow, and cost together.

## What can be reproduced

The dashboard opens without an ElevenLabs account or key. Published files are reviewed projections with substituted IDs, omitted metadata, and English translations. The aliases cannot resume runs in the original account.

Use the runner with your own agent, credentials, and settings following the [adaptation guide](ADAPTATION.md). The study's complete agent configuration, institutional knowledge base, and original integration are not included as reproducible infrastructure.

Criteria were refined during the study. Check signatures and input snapshots before comparing batches, including their language provenance. Repeated evaluations can reveal variability; an isolated pass does not establish stability or production performance.
