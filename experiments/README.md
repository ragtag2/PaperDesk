# Agent evaluation fixtures

Prepared: 2026-10-08.

This folder contains the frozen experiment data, seed script, full-agent runner,
deterministic evaluators and evaluation rules. The runner was prepared without
executing Python, tests, dependency installation, agent analyses or Langfuse
operations. The user has already successfully seeded `paperdesk_eval`.

The agent is configured in `agents/.env` to use
`openai:lightning-ai/deepseek-v4.1-flash` at `https://lightning.ai/api/v1/`, matching
`light.py`. The runner uses the same agent settings. The V1 baseline records the
model and endpoint, and requires them to remain fixed for V2 and V3. The Lightning
credential stays in the local environment; it is not experiment metadata.

## Files

| File | Contents |
| --- | --- |
| `teams.csv` | Six teams with explicit responsibility boundaries. |
| `users.csv` | Fifteen synthetic users: twelve active team members, two inactive members in different teams, and one active unassigned user. |
| `tickets.csv` | Ten tickets with reference answers, required facts and evaluation notes. |
| `seed.py` | Manually invoked loader for the fixed `paperdesk_eval` database. |
| `import_directory.py` | Import only fixture teams/users into `paperdesk`, preserving Akrem/Rayen and existing tickets. |
| `run.py` | Manually run one full-agent V1, V2 or V3 round linked to a Langfuse dataset. |
| `check_model.py` | Manually isolate model endpoint, token-parameter and initial tool-call failures without database or experiment calls. |
| `evaluators.py` | Five independent deterministic score functions. |
| `requirements.txt` | Seed and runner dependencies, including the agent requirements. |
| `EVALUATION_RULES.md` | Deterministic checks, judge rubrics and comparison rules. |

## Cases

| Case | Coverage | Expected teams |
| --- | --- | --- |
| E01 | Straightforward peripheral fault | IT Support |
| E02 | Straightforward central MFA failure | Security & Access |
| E03 | Straightforward financial records correction | Finance |
| E04 | Application defect and payroll impact | Business Applications; Finance |
| E05 | Network fault and dispatch impact | Infrastructure; Operations |
| E06 | Suspected security incident and dispatch impact | Security & Access; Operations |
| E07 | Application symptom with unknown cause/impact | Business Applications |
| E08 | Authentication symptom with unknown cause/impact | Security & Access |
| E09 | Personal question without workplace involvement | None |
| E10 | Updated issue with obsolete coordination | Finance |

## CSV format and reference data

Files are UTF-8 CSV with a header and one record per line. JSON cells use normal
CSV quote escaping; parse the CSV before parsing those cells as JSON.

All MongoDB IDs are fixed lowercase ObjectId strings. Empty user `teamId` and
ticket `assigneeId` cells mean null. `isActive` contains true or false.
The seed converts IDs to ObjectIds and timestamps to UTC datetimes.

`expected_answer_json` contains the full expected agent response:
`ticketId`, `summary`, `relevantTeams` with reasons, and `stakeholderUserIds`.
IDs are exact references; text is illustrative and judged by meaning.
The required-fact columns and evaluation notes define that meaning.

Evaluation-only columns are kept in this folder. The ticket documents inserted
into MongoDB contain only ordinary application fields plus the intended previous
coordination. Nine previous-coordination values are null; E10 includes Security
& Access and Finance from an earlier MFA incident, while its current reference
selects Finance alone.

## Manual seed instructions

The existing experiment database is already seeded. These commands are retained
as setup/restoration instructions; running the experiment does not require
seeding it again. The assistant has not executed them.
Use Python 3.11 or newer. From the project root, using the existing agent virtual
environment in PowerShell:

```powershell
.\agents\.venv\Scripts\python.exe -m pip install -r .\experiments\requirements.txt
.\agents\.venv\Scripts\python.exe .\experiments\seed.py
```

The default env file is `agents/.env`. The script reads `MONGODB_URI` and
optional `MONGODB_DNS_SERVERS`; existing process variables take precedence.
It does not need agent-model or Langfuse credentials. An alternative env file
can be selected explicitly:

```powershell
.\agents\.venv\Scripts\python.exe .\experiments\seed.py --env-file .\experiments\.env
```

The destination is always `paperdesk_eval`, regardless of `MONGODB_DB_NAME` or
the URI's default database. The script validates all CSV records and reference
memberships before connecting, then checks for documents outside the fixture
before any writes. Use an empty evaluation database or one already containing
only these stable fixture IDs.

Seeding upserts teams, users and tickets by their fixed IDs. Re-running restores
their fields and the intended previous coordination. It creates the user email
uniqueness and membership indexes. Dates are fixed: created at
2026-10-01T09:00:00Z and updated at 2026-10-08T09:00:00Z. E10's previous analysis
is dated 2026-10-07T09:00:00Z.

The shared user schema requires password hashes. Seeding generates valid bcrypt
hashes from random passwords that are not retained, so these users serve as
membership fixtures rather than accounts with known login credentials. Hashes
are regenerated on each seed; the agent does not read them.

Writes span three collections and are not a transaction. If seeding is
interrupted, rerun it to finish restoring the fixture.

## Import the directory into the application database

`import_directory.py` is separate from the evaluation seed. Its destination is
always `paperdesk`; it uses `MONGODB_URI` and optional `MONGODB_DNS_SERVERS` from
`agents/.env`, with the same `--env-file` option and process-environment precedence.
It reads and validates the fixtures but writes only teams and users.

```powershell
# Read-only account/collision check.
.\agents\.venv\Scripts\python.exe -B .\experiments\import_directory.py
# Apply and verify the directory import in a MongoDB transaction.
.\agents\.venv\Scripts\python.exe -B .\experiments\import_directory.py --apply
```

The import requires one existing account whose name starts with Akrem and one
whose name starts with Rayen. It leaves both with explicit `teamId=null`,
preserving their IDs, password hashes, roles and all other account fields except
the membership update timestamp. Existing unrelated teams and users are retained.
Fixture records use the CSV IDs; conflicting IDs, emails or team names stop the
import before writes. Repeating an import updates fixture profile fields while
preserving existing password hashes, session versions and creation timestamps.

New fixture users keep the CSV roles, memberships and active/inactive flags.
The required `passwordHash` is generated from a discarded random value; there
are no provided or retained login passwords. The transaction verifies all 21
fixture records, protected accounts and a fingerprint of existing tickets before
committing. It requires a replica set or sharded cluster, including MongoDB Atlas.
No evaluation tickets, expected answers or judge context are imported into
`paperdesk`; the experiment database and Langfuse setup remain separate.

## Your Langfuse setup

Use each row's `case_id` as its human-readable case identifier and its ticket
ObjectId as the agent input. The agent's input remains `{ "ticketId": "..." }`.
Use the parsed reference answer as expected output and keep the required facts,
evaluation notes and frozen team descriptions available to the evaluators.

The experiment agent must explicitly use `MONGODB_DB_NAME=paperdesk_eval`.
Use its read-only analysis path so outputs do not overwrite seeded coordination.
Judge input must contain the frozen ticket/team evidence as well as the actual
output; the ticket ID alone does not provide enough judging context.

Follow `EVALUATION_RULES.md` for scoring. Run V1, review its failures, develop V2,
run it, then develop and run V3. Langfuse configuration and execution remain
user-managed; prompt revisions are made only after reviewing the prior round.

## Run one round manually

Use the existing agent virtual environment. `requirements.txt` includes the
agent dependencies; install it only if that environment is missing dependencies.
The runner reads `agents/.env` through the existing Settings loader. It needs
MongoDB, the configured agent-model credentials, and both Langfuse keys, with
`LANGFUSE_TRACING_ENABLED=true`. It forces its own database destination to
`paperdesk_eval` without editing `.env` or changing the normal service database.

Create the dataset yourself in Langfuse. It must contain exactly ten active
items, each with Input `{ "ticketId": "<ticket ObjectId from tickets.csv>" }`.
A JSON-encoded object or bare 24-character ticket-ID string is also accepted and
normalized into that object locally. An exact integer is accepted only when its
complete 24-digit ID matches a fixture; floats and unknown IDs are rejected.
Keep IDs quoted in Langfuse so numeric parsing does not change their digits.
Duplicate, missing and unknown tickets are rejected before model calls.
Optional Expected Output must match the parsed
CSV reference (array order and ID case are ignored). If it is empty, the runner
supplies the CSV answer in memory. It does not create or modify hosted dataset
items, prompts, connections, evaluators or rules.

The runner builds each case's full context from the CSVs in memory. SDK item
metadata initially contains only small case labels and eligibility flags, because
the SDK propagates those values with a 200-character limit. When the task starts,
the runner attaches the full context directly to that case observation and its
local item copy. No ticket, team, reference answer or required fact is shortened.
Both judges continue to map context to the observation's entire Metadata object.
The Langfuse SDK creates the dataset experiment and links its task observation to
the dataset item. The runner names that task observation `paperdesk-eval-case`,
records the full output there, and lets SDK evaluator functions attach all five
deterministic scores to that same observation. The normal model, database tools,
team validation, stakeholder assembly and local analysis reporting still run.

Run V1 using the exact builtin `SYSTEM_PROMPT`:

```powershell
.\agents\.venv\Scripts\python.exe .\experiments\run.py --dataset "YOUR_DATASET_NAME" --round V1 --run-name "paperdesk-V1"
```

After reviewing V1, create a **text prompt** in Langfuse containing the improved
agent system instructions, without unresolved template variables. Supply its
actual name and numeric version; `ticket-analysis-system` and version `2` below
are examples to replace with your values:

```powershell
.\agents\.venv\Scripts\python.exe .\experiments\run.py --dataset "YOUR_DATASET_NAME" --round V2 --run-name "paperdesk-V2" --prompt-name "ticket-analysis-system" --prompt-version 2
```

After reviewing V2, run V3 with the next chosen prompt version:

```powershell
.\agents\.venv\Scripts\python.exe .\experiments\run.py --dataset "YOUR_DATASET_NAME" --round V3 --run-name "paperdesk-V3" --prompt-name "ticket-analysis-system" --prompt-version 3
```

V1 can also use a pinned Langfuse text prompt, but its compiled text must match
the builtin prompt exactly. Each round fetches the selected prompt once. V2 and
V3 require an explicit prompt name/version; no mutable `latest` label is used.
The prompt replaces the agent system instructions for that coordinator instance.
Judge prompts and reference answers are never sent to the agent.

Use a unique run name for each invocation. The runner executes one round and one
case at a time (`max_concurrency=1`), with a default minimum 25 seconds between
case starts. Change `--interval-seconds` if your model provider requires a longer
interval. It does not automatically retry or launch the next round.

An optional `--dataset-version "<UTC ISO timestamp>"` pins a hosted dataset
snapshot. Use the same timestamp for each round when you choose this option.
Every round validates the actual database against the local fixture. Real tool
results are also checked for ticket, team and active-member changes. There are
no MongoDB writes, so the intended previous coordination remains intact.

The first V1 records a baseline under the ignored
`agents/runs/experiments/<dataset-hash>/baseline.json`. Later rounds require the
same CSV content, evaluation rules, agent/runner source, package versions and
agent model settings. Save that baseline when working across machines. Keep the
judge definitions, model/settings and rule mappings fixed yourself in Langfuse.

The runner saves a dated JSON report beside the baseline and prints deterministic
pass counts and the dataset run link. Reports contain per-case output, context,
timing, trace ID, scores and mismatch explanations.
Use `analysis_seconds` for analysis latency; the SDK task duration also includes
fixture checks and any wait between cases. Model/token metrics remain available
on the child `ticket-analysis` observation and the existing local analysis report.
An agent failure returns
five deterministic zeros. Fixture/setup errors are tracked as infrastructure
errors; evaluator errors leave missing scores rather than becoming quality zeros.
A nonzero process exit indicates an execution/evaluation error, missing case or
missing dataset linkage. A complete run with quality mismatches can still exit
successfully. LLM judge scores arrive asynchronously in Langfuse and are not
included in the local report.

## Diagnose a failed model connection before repeating V1

If the first model call fails for all ten tickets, the zeros describe execution
failures; they do not establish prompt quality. Diagnose the connection first:

```powershell
.\agents\.venv\Scripts\python.exe .\experiments\check_model.py
```

This reads `agents/.env` and makes at most six model requests, stopping at the
first failure: a minimal request matching `light.py`, the configured temperature
and token limit with `max_tokens`, the same request with `max_completion_tokens`,
a simple automatic echo tool call, a follow-up with an artificial echo result,
and the actual agent's initial tool schemas. The installed ChatOpenAI adapter
sends `max_completion_tokens`.

The user's minimal and token-limit probes passed, but forced agent tool selection
returned HTTP 500. LangChain requests `any` for ToolStrategy, which the OpenAI
adapter normally sends as `required`. DeepSeek documents that forced selection
is unsupported in thinking mode. The adapter for this exact Lightning model now
maps that choice to `auto` and preserves `reasoning_content` across tool exchanges,
while retaining the original tools and structured-result validation. This is a
likely compatibility fix; the Lightning behavior must be verified by the user.
[DeepSeek tool-selection API](https://api-docs.deepseek.com/api/create-chat-completion/),
[thinking-mode tool exchanges](https://api-docs.deepseek.com/guides/thinking_mode/).

To check only the three tool stages after completion checks already passed:

```powershell
.\agents\.venv\Scripts\python.exe .\experiments\check_model.py --tools-only
```

The output identifies the failing stage, shows the effective tool selection, and
includes a redacted error/body when available. No MongoDB, Langfuse, experiment,
seed or actual tool calls occur; the probe supplies the echo result directly.
Passing these probes does not verify full ticket analyses or output quality.

After resolving the model failure, repeat **V1** under a fresh run name. A code
fix changes the source hash, so archive the failed attempt's `baseline.json`
before creating its replacement. Keep the original report and hosted run as
failure evidence. For the reported all-failed run, these manual commands preserve
the old baseline and create a new V1 attempt; use them only after the model probe
passes:

```powershell
Move-Item -LiteralPath .\agents\runs\experiments\10b882cfbaf14c69\baseline.json -Destination .\agents\runs\experiments\10b882cfbaf14c69\baseline.failed-V1-20261008T212211.json
.\agents\.venv\Scripts\python.exe .\experiments\run.py --dataset "experiments prompt" --round V1 --run-name "paperdesk-V1-retry-1"
```

Do not replace a baseline containing a completed comparison run to allow code or
model changes between V1, V2 and V3. Complete a valid V1 before revising its prompt.

## Connect the existing LLM judges

Keep the two judge definitions and their numeric rubrics. Map:

| Variable | Observation source |
| --- | --- |
| `evaluation_context` | Entire **Metadata** object |
| `assistant_output` | Entire **Output** object |

Metadata contains `ticket`, `teams`, `required_summary_facts`,
`required_reason_facts`, `expected_answer`, `evaluation_notes`, case/run
identifiers and completion flags. These come from the local fixtures, not from
the agent's summary or earlier analysis. Reference data is stored only in
evaluation telemetry and is absent from agent-visible database tool responses.

Use the rule Builder to target observation **Name = paperdesk-eval-case**.
Use that name rather than relying on the default root-observation filter; this
SDK task has a parent observation. Set sampling to **100%** and add these
metadata filters:

| Judge | Required metadata filters |
| --- | --- |
| `summary_quality` | `evaluation_ready` equals the string `true` |
| `reason_quality` | `evaluation_ready` equals `true` and `reason_applicable` equals `true` |

The flags deliberately contain strings, not JSON booleans. Failed analyses have
`evaluation_ready=false`. When expected and returned team lists are both empty,
`reason_applicable=false`, so reason quality is N/A. Unexpected teams on E09
remain eligible for reason scoring. Both judges see the full response, including
all returned team reasons. Select a completed experiment case to inspect the
mapped previews and test your judges.

References: [SDK experiments](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk),
[judge mappings and rules](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge),
[prompt versions](https://langfuse.com/docs/prompt-management/features/prompt-version-control).

## Prepared offline verification

Tests cover fixture/reference answers, failed and empty outputs, selection versus
membership errors, inactive/unassigned users, duplicate IDs, schema violations,
ID normalization, dataset mismatches, judge eligibility, and agent prompt
overrides/defaults. They were prepared but have not been executed.

If you choose to run those tests yourself, from the project root:

```powershell
.\agents\.venv\Scripts\python.exe -m unittest agents.tests.test_experiments agents.tests.test_agent agents.tests.test_tracing
```

## Branch command

From the project root:

```powershell
git switch -c feat/agent-evaluation
```
