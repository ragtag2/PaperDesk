# Run the tool evaluation study

Ticket 02 implements A-E on the existing coordinator. The expanded `paperdesk_eval`
database is already seeded and verified (12 teams, 32 users, 30 tickets). No
measured study has been run. Dataset import and the commands below are your steps.
Keep your existing evaluator setup unchanged.

## 1. Add the twenty new Langfuse items

Keep the original ten dataset items and their IDs. Add only E11-E30 from
[`new-cases.csv`](../.scratch/tool-evaluation/new-cases.csv), or the last twenty
rows of `experiments/tickets.csv`.

For each added item:

- Input is a JSON object: `{ "ticketId": "<the complete _id column value>" }`.
  Keep the 24-character ID quoted; spreadsheet numeric conversion can corrupt it.
- Expected Output is the parsed JSON in `expected_answer_json`. It can also be
  left empty: the runner supplies that reference locally without changing Langfuse.
- Optional metadata can include `case_id`. The runner attaches the full ticket,
  all twelve team responsibilities, required facts, references, and judging flags
  to the existing `paperdesk-eval-case` observation when execution starts.

The dataset must contain exactly thirty active items, with each fixture ticket
appearing once. The runner rejects duplicate, missing, unknown, or conflicting
items before any model work. It never imports or edits hosted items for you.

## 2. Finish implementation before freezing measured runs

Ticket 03 adds comparable resource attribution and usage availability; ticket 04
imports asynchronous judge scores and builds the comparison. Complete those
changes before starting the final measured study so all five runs use the same
instrumentation and source snapshot. This guide supplies the commands now; it
does not automatically start them or fill missing attempts.

Use the existing agent virtual environment and `agents/.env`: MongoDB URI, agent
model credentials/settings, Langfuse URL/keys, and `LANGFUSE_TRACING_ENABLED=true`.
The runner always reads `paperdesk_eval`, independently of the normal service's
database setting. It fetches the existing `ticket-analysis-system` text prompt at
numeric version **3**, without changing prompt versions or labels.

From the project root in PowerShell, set the actual dataset name and one study ID:

```powershell
$evaluationDataset = 'experiments prompt'
$evaluationStudy = 'tools-20261013-01'
$evaluationArgs = @('--dataset', $evaluationDataset, '--study', $evaluationStudy, '--interval-seconds', '25')
```

Use one study ID for all five variants. Choose it once for the planned cohort;
do not create another study just to hide a failed or interrupted attempt.

## 3. Check prerequisites without model calls

```powershell
.\agents\.venv\Scripts\python.exe -B -m experiments.run @evaluationArgs --variant A --run-name "${evaluationStudy}-A" --check-only
```

This reads Langfuse and MongoDB, validates all thirty cases, and writes the local
`agents/runs/experiments/tool-evaluation/<study>/manifest.json`. It constructs no
model and runs no cases. Review its `profiles` and `retrieval_diff` entries.

The manifest freezes the fixture/reference and normalized dataset hashes, item
identities/groups, model settings, source/dependency versions, all five profiles,
actual database-tool schemas, base V3 prompt, and effective prompts/hashes. A/B
retain V3 exactly; C-E replace only its recognized retrieval sentence. Unrecognized
wording is rejected rather than silently rewriting coordination policy.

The hosted judge configuration remains operator-managed: this runner freezes
local evaluation code/rules but does not automatically detect hosted judge edits.
Keep those existing definitions, model settings, and mappings fixed across runs.
No evaluator setup is required by these commands.

## 4. Run each variant once, explicitly

These are the measured commands. Run them yourself, one at a time, after the
prerequisite check succeeds. Review each command's exit status and report before
launching the next. They schedule **30 analyses each, 150 total**; each analysis
can make multiple model requests.

```powershell
.\agents\.venv\Scripts\python.exe -B -m experiments.run @evaluationArgs --variant A --run-name "${evaluationStudy}-A"
.\agents\.venv\Scripts\python.exe -B -m experiments.run @evaluationArgs --variant B --run-name "${evaluationStudy}-B"
.\agents\.venv\Scripts\python.exe -B -m experiments.run @evaluationArgs --variant C --run-name "${evaluationStudy}-C"
.\agents\.venv\Scripts\python.exe -B -m experiments.run @evaluationArgs --variant D --run-name "${evaluationStudy}-D"
.\agents\.venv\Scripts\python.exe -B -m experiments.run @evaluationArgs --variant E --run-name "${evaluationStudy}-E"
```

| Variant | Model database tools | Supplied context, alongside ticket ID |
| --- | --- | --- |
| A | get_ticket, list_teams, get_team_members | None |
| B | get_ticket, list_teams | None |
| C | list_teams | Current ticket |
| D | get_ticket | Team directory |
| E | None | Current ticket and team directory |

Python always checks ticket existence, validates selected teams, and assembles
every active member of those teams, with deduplication and inactive/unassigned
exclusions. The existence-check ticket supplies C/E's preload; D/E reuse their
directory preload for validation. Fixture audits run before and after each
successful analysis, outside its measured interval, and also catch changes to
cached context during the last case. All reads use the ordinary database-tool
projections and callbacks, including intended previous coordination. No answer
keys or evaluator notes reach the model. E still returns structured output.

Each run uses one worker and a 25-second minimum interval between case starts.
Case order is E01-E30; the commands above use A-E order. Use the same interval,
facts, dataset snapshot, and settings throughout. If you supply an explicit
`--dataset-version '<UTC timestamp>'`, include it in `$evaluationArgs` before
the first check and keep it fixed for every run.

There are no MongoDB writes, automatic model retries, extra smoke analyses, or
automatic launches of the next variant. A run name is a label; `--variant`
selects behavior. The local `attempt-<variant>.json` marker prevents accidentally
repeating a variant or reusing a run name within the same study. A preflight
failure does not claim an attempt; `--check-only` is safe to repeat.

## 5. Inspect the saved results

Each run writes a dated JSON report under the study directory, with thirty
stable case/item identities, regression/held-out groups, variant/settings,
outputs, errors, deterministic scores, and analysis/report/trace linkage.
SDK failures or interruptions retain completed task outputs and explicit missing
slots; absent SDK scores/linkage stay absent. The runner does not replace them.

A nonzero exit means execution, infrastructure, scoring, or linkage is incomplete.
Stop and inspect the report; do not delete attempt markers or rerun a variant
without deciding how the additional attempt will be recorded. A complete run
can exit successfully while containing quality mismatches.

Summary/reason judges run asynchronously through the existing Langfuse rules.
Their scores remain pending in the local report until ticket 04's reconciliation.
Ticket 03 is responsible for comparable resource attribution and missing usage;
the current combined metrics alone should not be used to claim resource savings.
Historical V1/V2/V3 reports and `baseline.json` are preserved separately.
