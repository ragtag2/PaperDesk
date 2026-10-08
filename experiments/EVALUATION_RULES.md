# Paperdesk evaluation rules

Prepared: 2026-10-08. These are the scoring rules for the ten CSV cases.
Langfuse dataset setup, evaluator configuration and experiment execution are user-managed.

## Team-selection policy

Select a team when the current ticket provides evidence that it owns work needed
to handle the issue or that its business work is clearly affected. Include both
responsible and clearly affected teams. Use the responsibility boundaries in
`teams.csv`.

A team name, the creator's membership, the ticket category or a business
application being mentioned is insufficient by itself. An unknown technical
cause does not prevent selecting the team that owns the explicitly reported
symptom. Preserve uncertainty about cause, scope and business impact.

For E10, current ticket facts supersede the earlier coordination. The old
coordination remains historical context; its teams are reassessed.

## Reference answers and evaluator context

Each `tickets.csv` row includes:

- `expected_answer_json`: a reference CoordinationResult with the exact expected
  team and stakeholder sets and example summary/reason wording.
- `required_summary_facts_json`: facts a correct summary must preserve.
- `required_reason_facts_json`: a map from expected team ID to evidence and
  responsibility facts a correct reason must communicate.
- `evaluation_notes`: case-specific boundaries and mistakes to watch for.
- `coordination_json`: actual previous coordination, null for nine cases and
  deliberately outdated for E10.

Parse JSON cells before comparison. Summary and reason wording may differ from
the reference; equivalent meaning is acceptable. Array order is irrelevant.

Judge inputs must include the actual output, frozen current ticket fields,
previous coordination marked as earlier context, the six team responsibility
descriptions, and the local reference facts/notes. Supply all team descriptions
so an unexpected selection can also be assessed. The agent receives only its
ordinary ticket/team/member tool data. The seed script excludes reference
answers, required facts, coverage labels and evaluation notes from MongoDB.

The implementation in `run.py` records this context in the Metadata of the
dataset-linked `paperdesk-eval-case` observation and the final CoordinationResult
in its Output. Existing judges map `evaluation_context` to the entire Metadata
and `assistant_output` to the entire Output. Target the completed case by name
with `evaluation_ready` equal to the string `true`, using 100% sampling. The
reason judge also requires `reason_applicable` equal to the string `true`.
These fields are observation metadata; evaluation rules do not retrieve CSVs or
child-tool observations themselves. `evaluators.py` supplies deterministic scores
through the experiment SDK on the same dataset-linked task observation.

## Deterministic evaluation

Evaluate the final full-agent CoordinationResult, after stakeholder assembly,
against the frozen fixture. Normalize valid ObjectId strings to lowercase.
Check duplicates separately before comparing sets.

| Score/check | Rule |
| --- | --- |
| `execution_success` | 1 if the analysis completes and returns a result; otherwise 0. |
| `team_exact_match` | 1 if the returned team-ID set equals the reference team-ID set; otherwise 0. Report missing and extra IDs separately. |
| `stakeholder_expected_match` | 1 if the returned stakeholder-ID set equals the reference stakeholder-ID set; otherwise 0. |
| `stakeholders_match_selected_teams` | 1 if returned stakeholders equal the union of all active users in the actually selected teams; otherwise 0. Derive this independently from `users.csv`. |
| `application_valid` | 1 only when execution succeeds and all structural/membership rules below pass; otherwise 0. |

Application validity requires:

- Exactly the current response fields: `ticketId`, `summary`, `relevantTeams`,
  and `stakeholderUserIds`; the ticket ID matches the case.
- Nonempty summary text; arrays for teams and stakeholders.
- Every team entry has exactly `teamId` and nonempty `reason`.
- All IDs have valid ObjectId format. Team IDs belong to `teams.csv`; stakeholder
  IDs belong to `users.csv`.
- Unique team IDs and unique stakeholder IDs.
- Stakeholders are all active members of the selected teams. Exclude inactive
  members, unassigned users and users from unselected teams.

Keep team correctness separate from application validity. An incorrect team
selection can still have correctly assembled membership; the expected-members
check exposes that difference. Existing agent self-checks are diagnostic data,
not an independent reference evaluator.

For E09, both expected sets are empty. Two empty sets match exactly. A returned
summary is still required. For E10, Security & Access and its two active members
must be removed from the current result; Finance remains.

Do not use LLM judges for IDs, membership, duplicates, enums or schema checks.

## LLM-as-a-Judge: summary quality

Score `summary_quality` using these fixed levels:

| Score | Meaning |
| --- | --- |
| 1 | Preserves all required summary facts, describes the current issue and stated impact accurately, handles unknowns correctly, and is concise and useful. |
| 0.5 | Factually supported and describes the central current issue, but omits a required detail or contains distracting repetition. |
| 0 | Misstates the central issue or current state, or invents a cause, affected department, scope, resolution or other material fact. |

Accept paraphrases and ordinary grammar improvements. A short summary of one to
three sentences is a useful target, not a hard word-count check. Earlier
coordination must not be presented as an ongoing issue when the current ticket
says it is resolved. The personal-weather case should summarize the request,
without generating a forecast.

The judge should return the numeric score and a brief explanation identifying
the evidence or omission that determined it.

## LLM-as-a-Judge: reason quality

Assess `reason_quality` for each returned team using its actual reason, current
ticket evidence and that team's responsibilities:

| Score | Meaning |
| --- | --- |
| 1 | Gives a specific, supported connection between ticket evidence and the team's responsibility or stated business impact, preserving relevant uncertainty. |
| 0.5 | The connection is supported but generic or incomplete, such as omitting the specific blocked process. |
| 0 | The connection is unsupported, contradicts the current ticket, invents facts, relies only on the team name, or retains obsolete involvement. |

For expected teams, use `required_reason_facts_json` to assess completeness.
For extra teams, assess whether the actual ticket supports their involvement;
a convincing-sounding explanation cannot fix deterministic selection errors.
Missing expected teams are reported by deterministic checks.

The case-level score is the arithmetic mean of its returned team-reason scores.
If a case requires teams but the agent returns none, use 0. If both expected and
returned selections are empty, mark reason quality not applicable and exclude
it from reason-quality averages. If E09 returns any teams, score their reasons
normally against its absence of relevant workplace evidence.

Return a score and short evidence-based explanation per returned team, plus the
case-level aggregate.

## Thresholds and sequential comparison

A case passes the deterministic category when execution, exact team match,
expected stakeholder match and application validity are all 1. A fully passing
case also requires summary quality 1 and reason quality 1 or not applicable.

Use the same ten cases, references, rules, thresholds, agent model/settings,
tools and application code across V1, V2 and V3. Keep the judge model/settings
and evaluator context fixed. Record the chosen model/settings before V1.

1. Run the current agent prompt as V1 and inspect all cases and traces.
2. Revise the prompt for the observed weaknesses and run V2 on all ten cases.
3. Revise from V2's remaining weaknesses and run V3 on all ten cases.

Prompt examples must come from outside these ten cases. Develop each revision
after reviewing the previous round; preserve each version for comparison.

Compare team exact-match count first, then regressions per case, membership and
validity failures, summary/reason quality, and finally latency/token usage.
An extra correct case changes ten-case accuracy by ten percentage points.

Record failed agent executions as failures for execution and exact-correctness
scores. Do not send nonexistent outputs to judges. Track evaluator errors
separately from agent quality scores and keep completion counts visible.
Reason averages must show their applicable-case count.

These cases are used for iterative development. Results describe this pilot;
performance on unseen tickets needs a later untouched dataset.
