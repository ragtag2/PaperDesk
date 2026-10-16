# Tool evaluation plan

Updated: 2026-10-13.

Status: Design in progress. This document records agreed scope and unresolved decisions. The expanded evaluation has not been implemented or executed.

## Agreed scope

- Determine which database tools the model needs by comparing output quality, cost, latency, and unnecessary calls. Comparison conditions should have access to the same frozen ticket and team facts.
- Use 30 distinct ticket cases: the original 10 for regression checks and 20 new held-out cases.
- Keep the new 20 cases out of prompt tuning until the planned comparison is finished. Use all 30 cases together for the primary comparison, with separate regression and held-out breakdowns retained.
- Expand to 12 teams by adding HR, Procurement, Facilities, Legal & Compliance, Customer Support, and Data & Analytics to the existing six. Define clear responsibility boundaries and varied memberships, including inactive users and a team with no active members. Exact boundaries and membership counts remain open.
- Use the existing V3 prompt, ticket-analysis-system version 3, and the pilot's fixed model/settings. Preserve its coordination instructions, adjusting only the wording required for each tool/context condition.
- Keep team exact-match rate, mean summary score, and mean team-reason score separate. Describe a variant as improved when at least one aggregate quality metric improves and none declines. If all three tie, cost and latency can distinguish the configurations. Individual case regressions may accompany aggregate improvement; report each case's gains and losses.
- The study compares and observes tool configurations. Report failed analyses, schema errors, and stakeholder membership failures alongside quality, cost, and latency. No automatic winner or acceptance gate is part of the current design.
- Run each variant once on all 30 cases: five separate experiment runs and 150 total case executions. No additional repetitions are planned.

## Evaluation terminology

- Case: one frozen ticket scenario with its expected coordination and grading context. The suite has 30 distinct cases.
- Variant: one configuration of model-accessible database tools and upfront ticket/team context, labelled A through E.
- Experiment run: one variant evaluated once on every case in the suite. A complete run contains 30 case executions.
- Case execution: one full analysis of one case under one variant, including deterministic reads, model/tool calls, validation, and stakeholder assembly. It may contain multiple model requests.

Use these terms instead of the ambiguous word "pass".

## Tool comparison design

The user indicated that A is valid and B-E are valid provided deterministic stakeholder assembly is retained. This design satisfies that condition by changing only the model-accessible tool list and supplied context, while retaining Python's database capabilities.

| Variant | Database tools available to the model | Data supplied before the model call |
| --- | --- | --- |
| A | get_ticket, list_teams, get_team_members | None |
| B | get_ticket, list_teams | None |
| C | list_teams | Current ticket |
| D | get_ticket | Team directory |
| E | None | Current ticket and team directory |

C and D each start from B. E combines their upfront context. Preloaded context is fetched deterministically from the same frozen data used by the tools. References, required facts, and judge notes remain evaluator-only.

Python retains its ticket existence check, selected-team validation, and stakeholder assembly in every variant. Removing get_team_members from the model's choices leaves Python querying active members for every selected relevant team and combining unique user IDs. This covers both responsible and affected teams. Individual stakeholders are not inferred by the model. A selected team with no active members contributes no stakeholders.

The response schema and validation remain consistent across variants, including E. "No database tools" describes model database access; structured output remains enabled.

## Proposed run and comparison layout

Use one frozen 30-item Langfuse dataset and a separate named experiment run for each variant. Run names identify the condition; runner changes will be needed to actually select it.

| Example run name | Role | Case executions |
| --- | --- | --- |
| tools-A-r1 | Current-agent baseline | 30 |
| tools-B-r1 | Remove model access to membership | 30 |
| tools-C-r1 | Preload ticket; retain model directory retrieval | 30 |
| tools-D-r1 | Preload directory; retain model ticket retrieval | 30 |
| tools-E-r1 | Preload ticket and directory | 30 |

These five runs total 150 case executions. One run per variant is agreed; execution ordering remains open. A case execution may contain multiple model and tool calls.

A is a new baseline result on the expanded 30-case, 12-team fixture using V3's coordination instructions and the fixed model/settings. The historical ten-case V3 report remains pilot evidence; it cannot substitute for A on the new fixture. The runner's baseline.json configuration freeze is separate from the baseline result chosen for comparison in Langfuse.

Compare every other variant with A to assess the overall change from the current agent. Also use A versus B for membership-tool exposure, B versus C for ticket retrieval, and B versus D for directory retrieval. C versus E and D versus E show each retrieval choice when the other input is already preloaded.

Compare the same case across runs. Aggregate all 30 cases for the primary result and also report separate aggregates for the original 10 regression cases and 20 held-out cases. The held-out breakdown provides the view of cases unused in prompt development. Use fixed grading context and judge settings. Include deterministic preloading in end-to-end analysis latency. Track model costs and evaluation costs separately; the monetary accounting method remains open.

Langfuse supports comparing separately named experiments from a common dataset through aggregate metrics and per-item outputs/traces: https://langfuse.com/docs/evaluation/experiments/compare-experiments and https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk.

## Existing pilot evidence

- The pilot contains 10 distinct cases evaluated across three successful prompt rounds, V1, V2, and V3. All five deterministic checks passed for all cases in each successful round.
- Local experiment reports exclude asynchronous Langfuse summary and team-reason judge scores. Those judge scores and monetary cost figures have not been independently verified in this planning session.
- The model requested get_ticket and list_teams in every successful pilot case, and did not request get_team_members.
- Python separately checks ticket existence, validates selected team IDs, and assembles stakeholders from the active members of selected teams. Its initial ticket read is not supplied to the model under the current message construction.
- Every existing team has two active members. The pilot includes inactive and unassigned users, but no case selecting a team with zero active members.

Evidence: agents/agent.py, agents/tools.py, agents/reporting.py, experiments/users.csv, experiments/EVALUATION_RULES.md, and the saved V1/V2/V3 reports under agents/runs/experiments/10b882cfbaf14c69/.

## Decisions still open

- Responsibility boundaries and membership counts for the expanded organization; a proposal is in TOOL_EVALUATION_CASE_DESIGN.md.
- Exact condition-specific retrieval instructions and implementation of the agreed variant structure.
- Case coverage and review of expected answers against the final organization, including the original 10 cases; the new-case sketches remain proposed.
- Execution budget, ordering, and treatment of agent, tool, infrastructure, and evaluator failures.
- Fixed judge configuration and monetary cost accounting.
- Execution workflow and final confirmation of shared understanding before implementation.

## Implementation considerations for later

The current seed and runner enforce a ten-case fixture. The runner supports prompt rounds V1/V2/V3 and freezes tool/application source within their baseline; it does not yet support tool comparison variants. The expanded evaluation will need its own baseline, with the pilot records retained for historical context.

No experiment code, fixture CSVs, databases, or hosted Langfuse configuration have been changed by this planning document.
