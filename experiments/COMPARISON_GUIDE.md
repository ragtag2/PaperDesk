# Compare saved tool-evaluation runs

From the project root, generate an HTML report and case CSV using the existing
Langfuse scores and costs:

```powershell
.\agents\.venv\Scripts\python.exe -B -m experiments.compare --study agents/runs/experiments/tool-evaluation/tools-20261013-01 --fetch-langfuse
```

Open `comparison/comparison.html` inside that study directory. It is a standalone
file: no server, installation, or internet connection is needed to view it.
Select all thirty/original ten/new twenty cases, choose a comparison pair, filter
quality gains/regressions or incomplete evidence, and expand cases to inspect
outputs, judge explanations, checks, errors, resource evidence, and trace links.
The adjacent `cases.csv` has all 150 planned case/variant rows and A-relative
deltas. No winner is selected.

`--fetch-langfuse` makes read-only requests to the configured Langfuse v4
observations and scores APIs. It uses the keys in `agents/.env` and verifies that
the configured endpoint matches the frozen manifest. It requests only the saved
trace IDs and follows pagination. It never runs analyses, judges, seeding,
database writes, or hosted configuration changes. Every explicit fetch saves a
dated `langfuse-export-<timestamp>.json` snapshot alongside the report.

To rebuild entirely offline from a chosen snapshot:

```powershell
.\agents\.venv\Scripts\python.exe -B -m experiments.compare --study '<study-directory>' --export '<snapshot.json>'
```

You can also use CSV or JSON exports from Langfuse's Scores and Observations
tables. Include task/analysis observations, metadata, and generation usage/cost
fields in the observations export; exporting generations alone cannot recover
older runs' task linkage or analysis ancestry.

```powershell
.\agents\.venv\Scripts\python.exe -B -m experiments.compare --study '<study-directory>' --scores '<scores.csv>' --observations '<observations.csv>'
```

CSV headers can use camelCase or snake_case. Scores need `name`, `value`,
`traceId`, and `observationId`; retain `id` and `comment` when available. Observation
rows need `id`, `traceId`, `parentObservationId`, `name`, `type`, and `metadata`;
retain `totalCost`/`costDetails`, `usageDetails`, and `projectId`. JSON object cells
must contain valid JSON. V3 score exports with an observation `subject` are also
supported. An explicitly exported evaluator failure can use `status=error`, an
empty value, and a comment; absence alone stays pending, not error or zero.

Without score exports the command can produce an incomplete report with pending
judge scores. `--out '<directory>'` chooses a separate artifact directory.
Exactly one saved report per variant is accepted; missing variants/cases remain
visible. Duplicate runs, ambiguous scores/tasks, foreign records, and conflicting
study/facts/settings identities fail with an explanation. The importer does not
pick a latest run or overwrite source evidence. Rebuilding replaces only derived
HTML/CSV artifacts; source hashes and export provenance appear in the report.
Existing evaluator/version/job identities are retained and checked for
consistency per metric. Mixed judge configurations fail; missing identity
metadata is visibly marked unverified rather than claiming a validated freeze.

Quality means use scored eligible cases and show all completion counts. Reason
quality weights cases equally, remains N/A when both team sets are empty, and is
zero under the existing rubric when a completed output returns no required teams.
Fully scored team accuracy uses all planned cases; partial cohorts show counts
and coverage instead of claiming a complete rate. Deltas involving unavailable
data, and percentage changes from zero, remain N/A.

Agent cost sums each generation once under the exact saved analysis and checks
the generation count against recorded model calls. Partial exports retain known
subtotals and cannot claim complete cost savings. Values are Langfuse-reported
USD, potentially inferred using its configured prices, rather than verified
provider invoices. Historical effective pricing dates, cache pricing treatment,
and whether each cost was ingested or inferred are explicitly unavailable; the
report does not reconstruct historical pricing settings.
Judge spending is separate and remains N/A unless evaluator generations are
explicitly attributable in the imported trace. A scores-only export contains no
judge spending. The existing A-E runs predate ticket 03: combined database reads
remain inspectable, while detailed Python-read attribution stays unavailable.

One run per case/configuration supports descriptive observations. Run order,
caching, provider variability, and different judge eligibility limit conclusions.
Report generation does not rerun cases to fill gaps.

Offline validation:

```powershell
.\agents\.venv\Scripts\python.exe -B -m unittest agents.tests.test_comparison agents.tests.test_study
```
