# Expand agent evaluation to 30 cases and compare five tool configurations

Prepared: 2026-10-13.

Status: Implementation specification synthesized from the design discussion. Agreed requirements are binding; implementation proposals and unresolved decisions are identified explicitly. This specification does not authorize or claim that fixtures have been seeded, hosted configuration changed, or experiments executed.

## Problem Statement

The existing ten-case evaluation helped improve the agent's summaries and team explanations and, according to the user's results, reduce cost by approximately 12%. It evaluated prompt revisions rather than the contribution of individual database tools. Ten cases and a small, uniform organization provide limited coverage for determining which tools the model needs.

The user wants to expand to 30 distinct cases and observe how removing model access to database tools, while supplying the same ticket and team facts deterministically, changes coordination quality, cost, latency, and tool use. Stakeholder assembly must remain reliable in every configuration. The experiment must make trade-offs visible rather than automatically accept, reject, or deploy a configuration.

## Solution

Extend the existing full-agent evaluation workflow around the real model, the read-only evaluation database, and Langfuse. Retain the original ten cases, add twenty cases held out from prompt tuning, expand the organization to twelve teams, and evaluate five configurations once each.

Use one frozen 30-item dataset and five separately named experiment runs. Each run analyzes every case, producing 30 case executions; the complete study therefore schedules 150 case executions. A case execution can contain multiple model requests and tool calls. Judge calls are evaluation work, not additional agent case executions.

The primary comparison combines all 30 cases. Also report the original-ten and new-twenty groups separately. Keep team correctness, summary quality, and team-explanation quality as separate metrics, with failure counts and resource use alongside them. Preserve every case's output and changes so aggregate improvements do not conceal individual regressions.

## User Stories

1. As an experiment owner, I want thirty distinct cases, so that I can evaluate more situations than the original pilot covered.
2. As an experiment owner, I want to preserve the original ten cases, so that I can inspect changes on familiar regression cases.
3. As an experiment owner, I want twenty cases untouched by prompt tuning until the comparison finishes, so that I can inspect behavior beyond the development cases.
4. As an experiment owner, I want twelve teams with clear responsibilities, so that the agent must distinguish neighboring ownership boundaries.
5. As an experiment owner, I want varied memberships, inactive users, and a team with no active members, so that stakeholder assembly is exercised beyond uniform two-person teams.
6. As an experiment owner, I want to evaluate the current three-tool configuration, so that the study has a new baseline on the expanded fixture.
7. As an experiment owner, I want to hide the membership tool from the model while retaining Python's member lookup, so that I can measure the effect of exposing that tool.
8. As an experiment owner, I want to supply the ticket before the model runs, so that I can measure whether model-driven ticket retrieval adds value.
9. As an experiment owner, I want to supply the directory before the model runs, so that I can measure whether model-driven directory retrieval adds value.
10. As an experiment owner, I want to supply both inputs without exposing database tools to the model, so that I can observe coordination with deterministic retrieval.
11. As an experiment owner, I want every configuration to use the same frozen facts, so that different information does not explain the results.
12. As an experiment owner, I want the same V3 coordination instructions and model settings, so that the comparison focuses on tool access and input delivery.
13. As an experiment owner, I want stakeholders assembled from all active members of selected relevant teams, so that model guesses about individuals cannot change membership behavior.
14. As an experiment owner, I want one named run per configuration, so that I can compare the same case across five runs in Langfuse.
15. As an experiment owner, I want exactly one planned execution of each case/configuration pair, so that the study remains at 150 scheduled analyses.
16. As an experiment owner, I want team exact-match, mean summary score, and mean reason score displayed separately, so that a weighted score does not conceal quality trade-offs.
17. As an experiment owner, I want all thirty cases used for the primary result, so that the headline comparison matches the agreed design.
18. As an experiment owner, I want separate ten-case and twenty-case breakdowns, so that I can distinguish development-case behavior from held-out behavior.
19. As an experiment owner, I want failed analyses, invalid outputs, and membership errors reported, so that quality averages have visible operational context.
20. As an experiment owner, I want agent costs distinguished from judge costs, so that evaluator spending does not distort the tool comparison.
21. As an experiment owner, I want end-to-end latency to include deterministic retrieval and postprocessing, so that preloading does not receive an artificial timing advantage.
22. As an experiment owner, I want model-requested tools distinguished from Python's database reads and structured response calls, so that tool-use findings are interpretable.
23. As an experiment owner, I want per-case gains and losses with links to traces, so that I can investigate regressions even when averages improve.
24. As an experiment owner, I want references and judge notes excluded from agent inputs, so that the evaluation does not give the model its answer key.
25. As an experiment owner, I want data and configuration drift detected, so that accidental changes cannot silently enter the comparison.
26. As an experiment owner, I want missing and pending judge scores distinguished from zero scores, so that incomplete evaluation does not look like poor model quality.
27. As an experiment owner, I want observations without an automatic winner or deployment, so that I can decide what the measured trade-offs mean.
28. As an implementer, I want explicit module boundaries and validation requirements, so that I can implement the study without changing the product API.
29. As an experiment owner, I want unresolved choices listed before live execution, so that proposals are not mistaken for agreed decisions.

## Implementation Decisions

### Scope and terminology

**Agreed scope:** extend fixtures, fixture validation, experiment configuration, the full-agent runner, scoring context, telemetry, comparison reporting, and operator documentation. The production request/response contract remains unchanged.

| Term | Meaning |
| --- | --- |
| Case | One frozen ticket scenario and its evaluation references. There are 30 distinct cases. |
| Variant | A database-tool and upfront-context configuration, labelled A through E. |
| Experiment run | One variant evaluated once against the entire dataset. There are five planned runs. |
| Case execution | One full ticket analysis, including deterministic reads, model/tool exchanges, validation, and stakeholder assembly. |
| Coordinator | The existing Python IncidentCoordinator, which performs that full analysis; it is not another model or service. |
| Baseline result | Variant A's newly measured results on the expanded fixture. |
| Study manifest | The frozen configuration and provenance for this study; distinct from the baseline result. |

Use these terms instead of the ambiguous word "pass". A variant identifier must select behavior explicitly; a run name alone must not change tool access.

### Five agreed variants

| Variant | Database tools exposed to the model | Context supplied before the first model request |
| --- | --- | --- |
| A | get_ticket, list_teams, get_team_members | Ticket ID only; no upfront ticket or directory payload |
| B | get_ticket, list_teams | Ticket ID only; no upfront ticket or directory payload |
| C | list_teams | Ticket ID and current ticket |
| D | get_ticket | Ticket ID and team directory |
| E | None | Ticket ID, current ticket, and team directory |

C and D independently start from B. E combines their upfront inputs. "No database tools" in E does not remove structured output: the same TeamAssessment schema and structured-response mechanism apply to all variants.

Retain Python's ticket existence check, selected-team validation, and deterministic stakeholder assembly in every variant. Hiding a tool from the model must not remove Python's ability to call the underlying database operation. Both responsible teams and clearly affected teams contribute all their active members. Deduplicate stakeholders; exclude inactive, unassigned, and unselected-team users. A selected team with no active members contributes an empty member set, while remaining in relevantTeams.

Preserve the existing full database-tool registry and add a separate model-exposure selection. Do not implement B-E by deleting tools needed during Python postprocessing. A/B retain the existing behavior in which the initial Python ticket existence read is not model-visible. C/E can supply that read's ticket payload to the model. The exact reuse of directory reads for preloading and validation remains an implementation proposal to be fixed and recorded before execution.

### Fixed inputs and prompts

Use ticket-analysis-system version 3 as the common coordination prompt. Preserve its coordination policy, treatment of uncertainty, current-ticket precedence over outdated coordination, and handling of database text as evidence rather than instructions. Modify only retrieval wording necessary to tell each variant which tools or supplied inputs are available. Record the base prompt identity, the compiled prompt hash for each variant, and the retrieval-only difference. Do not move a production prompt label or tune the prompt after inspecting new-case outputs.

The pilot settings to preserve are:

| Setting | Frozen value |
| --- | --- |
| Agent model | openai:lightning-ai/deepseek-v4.1-flash |
| Model endpoint | https://lightning.ai/api/v1/ |
| Temperature | 0 |
| Maximum output tokens | 2048 |
| Request timeout | 20 seconds |
| Model retries | 0 |

Reuse the existing model adapter and structured-output behavior. Record dependency versions, source hashes, tool schemas, fixture/reference hashes, dataset identity/version, and all five retrieval profiles in one study manifest before measuring A. All runs must match its common settings and their declared variant-specific settings. Unexpected changes must fail preflight; do not weaken or overwrite the pilot's configuration freeze to permit the new study.

Variant A is a fresh baseline on the 30-case, 12-team organization. The historical ten-case V3 run is pilot evidence, not the baseline for this comparison. Preserve the old reports and their provenance.

### Fixture and organization contract

Retain E01-E10 and their stable ticket/case IDs as the regression group. Add E11-E30 as the held-out group. Preserve original ticket facts and starting coordination; review the references against the expanded directory before freezing. Any necessary reference correction must be documented rather than silently presented as an unchanged regression reference.

Retain the existing six teams and add HR, Procurement, Facilities, Legal & Compliance, Customer Support, and Data & Analytics. Clear boundaries, varied memberships, inactive users, and at least one zero-active-member team are agreed. Exact descriptions, user counts, and allocation are unresolved.

The existing draft proposes preserving the fifteen original users and adding seventeen, for thirty-two total:

| New team | Proposed responsibility | Proposed active / inactive members |
| --- | --- | --- |
| HR | Employee administration, leave policies/balances, and employee process decisions | 3 / 1 |
| Procurement | Sourcing, purchasing approvals, purchase orders, and replacement purchasing | 1 / 0 |
| Facilities | Premises maintenance, HVAC, lighting, and building electrical faults | 4 / 0 |
| Legal & Compliance | Contract review and explicit legal, regulatory, or compliance assessment | 0 / 1 |
| Customer Support | External inquiries, customer cases, and customer communications | 5 / 0 |
| Data & Analytics | Analytical datasets, reporting definitions, join/aggregation logic, and analytical data quality | 2 / 0 |

This distribution, including Legal & Compliance as the zero-active team, is a proposal, not an approved fixture requirement. The draft adds six straightforward, six cross-team, four boundary/incomplete-information, two outdated-coordination, one no-team, and one long/noisy case. Its exact case wording and references remain subject to review.

Each final case must contain ordinary current ticket fields and intended earlier coordination, plus evaluator-only expected team/stakeholder sets, illustrative summary/reason wording, required summary facts, required reason facts, evaluation notes, and a regression/held-out group. Summary and reason text is graded by meaning; IDs and memberships are exact references.

Validate JSON cells after CSV parsing, ID uniqueness and referential integrity, application field limits, role/active-state rules, complete required facts, and reference membership independently of agent self-checks. Replace the pilot's fixed six-team/fifteen-user/two-active-per-team assumptions with validation of the final approved organization. Preserve application-compatible shapes and the active unassigned exclusion case.

Seed only ordinary application fields into the fixed evaluation database paperdesk_eval. References, group/coverage metadata, required facts, and evaluation notes must not appear in MongoDB ticket documents or model messages/tool responses. Seeding remains a distinct, explicit operation; the runner must never seed or import data into the application database automatically.

### Module interfaces

The following are logical interfaces, not mandated new classes or packages. Prefer extending the existing modules and their public boundaries. New configuration/report capabilities are implementation proposals derived from the agreed behavior, not previously approved method signatures.

| Module or boundary | Inputs | Outputs and required behavior |
| --- | --- | --- |
| Fixture loader and validator | Local organization records, 30 ticket records, evaluation references, final suite requirements | Validated application records, evaluator-only case records, group mapping, and deterministic digests; rejects malformed or inconsistent data before network/model work. |
| Evaluation seeder | Validated application records and MongoDB connection | Fixed-ID upserts into paperdesk_eval only; rejects unexpected existing records and excludes all answer-key fields. |
| Variant resolver | One identifier A-E and the pinned V3 prompt | Model tool allowlist, ticket/directory preload policy, retrieval-adapted instructions, and configuration identity; rejects unknown identifiers and inconsistent profiles. |
| IncidentCoordinator construction | Existing database/model/tracing dependencies and prompt override, plus optional internal variant configuration | Ready full-agent coordinator. Existing callers retain current behavior when no experiment profile is supplied. |
| IncidentCoordinator.analyze | Valid ticket ID | Existing CoordinationResult: ticketId, nonempty summary, relevantTeams with teamId/reason, and stakeholderUserIds; preserves existing failure behavior and reports. No variant fields are added to the HTTP request or result. |
| Database adapter and read tools | Ticket ID, no arguments for the directory, or team ID for members | Existing serialized ticket, directory, or active-member payloads. Frozen experiment checks reject drift. Python access is independent of the model allowlist. |
| Experiment runner | Dataset identity/version, study identity, explicit variant, unique run name, frozen manifest, and pacing | One named Langfuse run covering exactly 30 cases, local per-case records, provenance, completion state, and error status; no prompt revision, seeding, or hidden additional runs. |
| Deterministic evaluator | Case request, final output or execution failure, reference answer, frozen teams/users | Existing five scores with missing/extra IDs and validity details. Invalid references are evaluator/configuration errors, not model-quality zeros. |
| Judge integration | Dataset-linked output plus frozen current facts, all twelve team descriptions, references, notes, and completion flags | Summary/reason scores and explanations from the fixed Langfuse evaluators; unavailable scores remain pending, failed, or not applicable explicitly. |
| Analysis telemetry | Model requests, tool events, Python read events, timing, result/error, study/run/case identifiers | Origin-attributed call records, token usage and availability, analysis duration, trace/analysis IDs, and optional cost with pricing provenance. |
| Comparison reporter | Five saved run records, matching judge scores/export, study manifest, and pricing inputs if available | All-30 and group aggregates, A-relative and ablation comparisons, per-case changes, completion/eligibility counts, failure categories, and report provenance; never calls the agent to reconstruct a missing result. |

Extend evaluation telemetry and local report formats without changing the product API or persisted coordination schema. Internal tool profiles belong to the experiment invocation, not browser or Express requests. The actual experiment uses the existing full coordinator, real model, and real read-only evaluation database; it must not substitute a fake model for any of the 150 measured executions.

### Evaluation workflows and Langfuse's role

1. **Prepare the content.** Finalize new team boundaries, memberships, ticket wording, and references. Recheck E01-E10. Derive expected stakeholders independently from expected teams and active memberships. Review all thirty before exposing held-out outputs to prompt tuning.
2. **Prepare the implementation.** Add explicit variants, separate study provenance, expanded fixture validation, telemetry, and comparison support. Prepare operator instructions and complete the validation checks below. This phase does not execute the measured study.
3. **Freeze the study.** Pin V3, the model/settings, all five retrieval adaptations, final facts/references, judge definitions/settings, dataset snapshot, dependency/source hashes, and run plan. Resolve the execution-affecting open points listed below.
4. **Prepare external state explicitly.** Seed or restore paperdesk_eval as a separate action. Prepare one frozen Langfuse dataset containing exactly thirty active, uniquely mapped fixture cases. The runner may normalize dataset items locally for SDK use while preserving item IDs; it must not silently edit hosted inputs or references. The operator responsible for these actions remains unresolved.
5. **Preflight each run.** Validate the requested variant and run identity, dataset completeness, references, database contents, prompt/profile hashes, and common settings. Fail before model work for known mismatches. Preserve the existing drift checks during reads; record any later mismatch as an integrity/infrastructure event.
6. **Execute the five named runs.** For each variant, analyze all thirty cases once. Example names are tools-A-r1 through tools-E-r1; the actual study names must be unique. A provides the new baseline. Run ordering, concurrency, pacing, and interruption handling remain to be fixed. The scheduled workload is five times thirty, not three prompt rounds and not fifteen repeated runs.
7. **Record each analysis.** Call the real coordinator. Include deterministic preloads, the actual model/tool loop, team validation, and Python stakeholder assembly. Capture the final result or error, metrics, and IDs linking the local report, Langfuse run, dataset item, task observation, and analysis trace.
8. **Score and reconcile.** Independent deterministic evaluators score the final result on the dataset-linked task observation. Existing asynchronous Langfuse rules score summaries and reasons. Reconcile judge scores with the correct task/run/case; distinguish pending evaluation from completed analysis. Reading/importing judge results must not rerun analyses.
9. **Compare and inspect.** Produce primary aggregates over all thirty and the separate ten/twenty breakdowns. Compare each variant with A and the tool-isolating pairs below. Show outputs, gains/losses, and trace links for individual cases. Report findings without selecting or deploying a winner automatically.

Langfuse is the shared dataset, experiment-run, tracing, and scoring surface. It does not replace the Python coordinator, read the local answer-key CSVs by itself, or assemble stakeholders. The runner supplies frozen evaluator context and final outputs to the dataset-linked observation. The local comparison artifact must incorporate judge scores or visibly state that they are missing; the current pilot report's exclusion of asynchronous judge results is insufficient for the requested full comparison.

Preserve the established observation name paperdesk-eval-case and its evaluation mappings unless a necessary compatibility change is documented. Map evaluation_context to the full task Metadata and assistant_output to its Output. Retain the string-valued evaluation_ready and reason_applicable flags, with 100% sampling for eligible tasks. Both judges see all twelve responsibilities. Failed analyses are ineligible for judges; cases with both expected and returned team sets empty are ineligible for reason grading but still eligible for summary grading.

### Scores, measurement, and interpretation

Retain these independent deterministic scores:

| Score | Meaning |
| --- | --- |
| execution_success | A full analysis returns a result. |
| team_exact_match | Returned team-ID set equals the expected set; disclose missing and extra teams. |
| stakeholder_expected_match | Returned stakeholder-ID set equals the expected set. |
| stakeholders_match_selected_teams | Returned stakeholders equal the independently derived active members of the actually selected teams, even if those teams are wrong. |
| application_valid | Final schema, ticket identity, ID validity/existence, uniqueness, and active membership constraints hold. |

Keep the existing numeric judge rubrics of 0, 0.5, and 1 for summaries and reasons. Summary scoring measures required facts, current issue/impact, uncertainty, accuracy, and concision. Reason scoring measures the supported connection between ticket evidence and team responsibility or business impact. Equivalent wording is valid. The case-level reason score remains the mean across returned team reasons; if teams are expected but none returned, it is 0. If both sets are empty, it is not applicable. Exact judge model, prompt/configuration snapshot, and settings must be pinned before execution.

For a fully analyzed run, team exact-match rate uses all thirty cases; failed analyses count as unsuccessful exact matches under the existing rules. Report the numerator and denominator. A missing execution due to an incomplete run or infrastructure interruption is not a completed model failure: show coverage and the missing status explicitly. Do not quietly drop missing records from the planned cohort or present a partial run as a complete thirty-case comparison.

Mean summary quality uses successfully judged eligible cases. Mean reason quality uses successfully judged applicable case-level scores, weighting cases equally. Always show eligible, scored, pending, evaluator-error, and not-applicable counts. Judge errors and missing scores are not zeros. Since eligibility can vary with outputs, expose the case-level scores and denominator differences; do not imply the means alone capture execution or team-selection failures.

**Agreed descriptive interpretation:** call aggregate quality improved when at least one of team exact-match rate, mean summary quality, and mean reason quality increases and none decreases. If all three tie, cost or latency can distinguish configurations. Individual regressions are permitted and must be listed. This describes observed results; it is not an acceptance gate, automatic ranking, or statistical proof. Incomplete evaluation must be identified before drawing this comparison.

Report failed analyses, schema/validity errors, unknown or duplicate IDs, incorrect stakeholder assembly, reference/evaluator errors, database/infrastructure failures, and missing reports separately. Preserve error stage/type and available usage. The policy for rerunning, resuming, or treating externally failed attempts in final comparisons remains unresolved; never silently replace an attempt or execute more analyses to fill a report.

For every case/run capture model request count; input, output, and cached-input tokens when provided; model-requested database tools; Python database reads by purpose; structured-response calls separately; and end-to-end analysis time. Distinguish a requested but rejected tool call from a completed database read. Preserve usage availability so unreported tokens/cost do not become a false zero. Existing combined tool-call fields may remain for compatibility, but cannot be the only attribution used in this study.

Measure analysis latency from before the ticket existence check/preloading through final validation and stakeholder assembly. Exclude inter-case pacing, fixture-audit overhead, and asynchronous judge latency from that analysis measure, and report study wall time separately. Include all model requests and deterministic work performed inside the analysis. Use the same boundaries for every variant. The exact summary statistics and treatment of partial/failed timings remain to be frozen.

Track agent-model cost and evaluator cost separately. Monetary results must state currency, provider/rate source, effective pricing date, cached-input treatment, and whether costs are provider-reported or estimated. Until that method is settled, report tokens and mark money unavailable rather than equating token reduction with dollar savings. Infrastructure cost accounting is also unresolved. Preserve available cost/usage for failed analyses.

Use origin-attributed call traces to investigate unnecessary calls. Repeated reads, model membership lookups despite deterministic assembly, and unrelated-team requests are observable review signals; do not automatically declare every occurrence unnecessary. The exact classification rule remains unresolved. Tool exposure may affect input tokens and behavior even when a tool is never called.

| Comparison | Interpretation |
| --- | --- |
| A versus each of B-E | Overall change relative to the current tool configuration on the expanded fixture. |
| A versus B | Effect of exposing get_team_members to the model. |
| B versus C | Effect of model-driven ticket retrieval versus supplying the ticket upfront. |
| B versus D | Effect of model-driven directory retrieval versus supplying the directory upfront. |
| C versus E | Directory retrieval when the ticket is already supplied. |
| D versus E | Ticket retrieval when the directory is already supplied. |

Pair records by stable case/dataset-item identity, not execution order or report row position. Show absolute values and deltas; if a relative-change denominator is zero or data is missing, mark the percentage unavailable. The study has one observation per case/configuration, so report variability and provider/cache/order limitations without claiming repeatability from a single run.

## Testing Decisions

### Boundaries and prior art

The measured evaluation boundary is agreed: the full coordinator with the real model, real read-only evaluation database, deterministic postprocessing, and Langfuse-linked scoring. Unit tests or scripted outputs cannot establish actual coordination quality or tool value.

The proposed implementation-check boundary reuses the full IncidentCoordinator.analyze operation and the existing runner/evaluator/report interfaces. Existing tests already exercise the real LangChain tool loop with a ScriptedChatModel returning predetermined tool calls and a database test double; experiment tests independently cover reference scoring, empty/failed results, membership versus selection mistakes, dataset mismatches, and judge eligibility. Tracing tests cover failures, postprocessing, and telemetry outages. Extend these patterns rather than introducing a parallel agent implementation.

Those offline checks verify program behavior before paying for measured runs; they are not another set of 150 experiments. Their purpose and distinction from the measured runs were clarified in the discussion. Read-only checks against paperdesk_eval are also valid for database integration and drift validation. The exact mix of offline checks and read-only integration checks is an implementation proposal, rather than a settled user decision. Do not add model-backed smoke analyses implicitly beyond the agreed execution count.

Good tests assert externally observable behavior: tools actually available to the model, facts actually supplied, returned coordination, scoring results, error classification, saved provenance, and report values. Avoid mirroring private helper structure, asserting incidental call ordering, or using an agent's own membership self-check as the independent oracle.

### Acceptance criteria for the implementation

These criteria determine whether the evaluation capability is implemented correctly. They do not require any variant to improve quality, reduce cost, or beat A.

1. **Suite:** the final fixture validates exactly thirty unique cases and twelve teams; the regression/held-out groups contain ten/twenty cases and use stable IDs. The approved membership distribution includes inactive, unassigned, and selected-zero-active-member coverage.
2. **Reference isolation:** persisted/tool-visible application data and model messages contain no expected answers, required facts, or evaluator-only notes. Upfront payloads contain the same ordinary ticket/directory facts as their tool equivalents.
3. **Profiles:** A-E expose exactly the database tools and upfront inputs in the variant table. Unknown or inconsistent profiles fail before model invocation. Structured output remains enabled for E.
4. **Postprocessing:** all profiles retain Python's existence check, team validation, deduplication, and union of every active member of selected relevant teams, including empty membership and no-team cases.
5. **Compatibility:** the existing analyze-ticket request/result and ordinary agent default behavior remain compatible. Experiment configuration does not leak into product endpoints or alter production prompt labels.
6. **Freeze:** the study has distinct provenance from the pilot, includes all five profiles and effective prompts, and detects undeclared fixture/reference, dataset, code/dependency, model, or judge changes.
7. **Run selection:** explicit variant selection controls behavior; run names are labels. Each planned run maps to all thirty dataset cases without duplicates, missing cases, or extra model executions hidden by the runner.
8. **Measured workload:** operator instructions describe five runs and 150 scheduled full-agent analyses. Repetitions, recovery, and additional model-backed checks are explicit rather than automatic.
9. **Real execution:** measured cases use the real configured model and evaluation database with full validation and stakeholder assembly. Evaluation execution performs no application-data writes.
10. **Deterministic scoring:** all five independent scores are retained, distinguish team selection from membership assembly, and produce missing/extra details. Invalid references are configuration/evaluator errors.
11. **Judge integration:** completed eligible outputs receive the frozen evaluator context and correct task linkage. Summary/reason score explanations, eligibility, and completion states are accessible to comparison reporting.
12. **Telemetry:** reports distinguish model database calls, Python reads, and structured responses; include usage availability and the agreed latency boundaries; link case, variant, run, analysis, and trace.
13. **Comparison:** reports provide the all-thirty primary view, ten/twenty breakdowns, each variant versus A, and the tool-isolating comparisons, with per-case gains and losses.
14. **Missing data:** failed analyses, incomplete executions, pending/failed judges, unavailable usage/cost, and reason not-applicability remain distinguishable and show counts/denominators.
15. **Interpretation:** separate quality metrics are preserved; no weighted quality score, automatic winner, disqualification rule, or deployment decision is introduced.
16. **Preservation and operation:** pilot reports remain intact; seeding, hosted setup, measured execution, and report reconciliation are separate documented actions. Unresolved execution prerequisites are visible before live work.

### Validation requirements

| Area | Required evidence |
| --- | --- |
| Fixture/reference consistency | Validate final record counts, stable regression IDs/facts, group membership, ID integrity, field limits, expected team boundaries, and independently derived active stakeholder references. Reject malformed or contaminated records. |
| Variant behavior | Exercise all five profiles through the full coordinator; inspect actual exposed tools and first-request context. For B-E verify model membership access is absent while Python assembly still succeeds; E completes through structured output. |
| Frozen facts | Compare preload payloads with the corresponding database tool projections. Check database/dataset/reference mismatches and mid-run drift produce explicit integrity errors. |
| Membership edges | Verify one and many selected teams, varied active counts, inactive and unassigned users, a selected zero-active team, no selected teams, deduplication, and stale coordination replacement. |
| Output and scoring | Verify correct output, wrong team selection with correct assembly, missing/extra members, duplicate/unknown IDs, invalid schema, empty selections, analysis failures, and invalid references receive the appropriate separate outcomes. |
| Judge eligibility | Verify summary eligibility for a successful no-team output, reason not-applicability when both sets are empty, zero reason score when teams are required but none returned, and no judging of nonexistent outputs. |
| Langfuse linkage | Confirm an existing completed task or the first planned measured case shows full current facts, all twelve responsibilities, output, flags, deterministic scores, and judge mapping on the correct dataset item/run. Avoid adding an unplanned smoke analysis. |
| Run cardinality | Verify dataset preflight rejects missing/extra/duplicate cases and report reconciliation retains all thirty planned rows per variant, including explicit missing/error states. |
| Measurement | With known test events, verify origin-attributed tool counts, structured-call separation, missing-usage handling, failed-request usage retention, timing boundaries, and cost provenance when enabled. |
| Comparison math | With constructed saved records, verify all-thirty and ten/twenty aggregates, equally weighted case reason scores, denominator/completion reporting, stable identity pairing, deltas, ties, trade-offs, individual regressions, and zero-denominator handling. |
| Compatibility and telemetry failure | Run relevant existing coordinator, experiment, tracing, database, and API contract tests. Verify telemetry failure does not discard a valid coordination and incomplete report export is visible. |
| Operator workflow | Review commands and documentation for separate fixture setup, dataset/judge setup, five explicit measured runs, score reconciliation, and report generation without hidden model/database-write operations. |

Implementation validation results must identify which checks actually ran, which used offline inputs, which used read-only integrations, and which remain pending. This documentation task performs static review only; none of the future runtime checks or measured runs are claimed complete.

## Out of Scope

- Prompt tuning on the new twenty cases before the comparison finishes.
- Additional repetitions, automatic retries/replacements of case analyses, or three new V1/V2/V3 prompt-development rounds.
- An automatic winning configuration, quality acceptance gate, weighted score, production tool change, or deployment.
- Changes to frontend behavior, Express endpoints, authentication, permissions, persisted coordination fields, or the public agent request/result shape.
- Removing Python's membership lookup, model inference of individual stakeholders, or giving reference answers to the agent.
- Seeding/importing experiment records into the application database, destructive cleanup, or changing hosted state as a side effect of generating this specification.
- Claims of statistical significance, guaranteed tool necessity, or validated dollar savings derived solely from this single-run design or token totals.

## Further Notes

### Unresolved points and their impact

| Point | Current state | Required resolution |
| --- | --- | --- |
| Organization details | Twelve teams and membership edge coverage are agreed; responsibility wording and proposed thirty-two-user allocation are unapproved. | Finalize before references and fixtures are frozen. |
| New cases and references | Twenty sketches exist; exact tickets, expected teams, required facts/reasons, and the old-reference review are unfinished. | Review and freeze before measured execution; do not tune on new-case outputs. |
| Retrieval adapters and read reuse | Tool/context profiles are agreed; exact retrieval-only wording, serialization, and directory-read reuse are implementation proposals. | Review minimal prompt differences and freeze behavior before A. Reuse of existing reads must be documented and included in telemetry. |
| Implementation-check mix | Existing full-coordinator and runner test patterns are proposed; fake components are only for checking code behavior, not measuring quality. | Select checks covering the validation requirements and identify any read-only integration dependencies. The measured workflow remains real model/database in all cases. |
| Judge configuration | Rubrics and fixed settings across runs are agreed; exact judge model, definitions/versions, and score-retrieval mechanism are not recorded. | Capture configuration and demonstrate mapping/reconciliation before interpreting summary/reason results. |
| Execution plan | One run per variant is agreed. Ordering, case order, pacing/concurrency, spend ceiling, and interruption handling are open. | Freeze a run plan before execution. Retaining the existing single-worker, 25-second minimum start interval is a proposal, not an agreement. |
| Failure and recovery policy | Failures must be visible and no automatic acceptance gate is wanted. Treatment of provider/tool/infrastructure interruptions, resume/replacement attempts, and incomplete comparisons is open. | Record attempts and missingness without silent reruns; any extra agent executions require an explicit change to the plan. |
| Money and latency summaries | Costs must be separate from judge spending and preloads must count in analysis latency. Pricing source/currency/cache rules, infrastructure accounting, timing summaries, and partial-failure aggregation are open. | Finalize accounting/statistics before reporting savings; tokens and raw timings remain reportable meanwhile. |
| Unnecessary calls | Tool value and avoidable calls are study goals; an operational classification rule is not agreed. | Define review criteria before classifying counts. Preserve raw origin-attributed events regardless. |
| Operator responsibilities | Earlier pilot setup was user-managed; ownership of expanded seeding, hosted setup, and measured execution has not been agreed. | State who runs each external action. This specification alone does not execute them. |

Unresolved content and execution choices do not prevent implementing the declared interfaces, validators, and draft workflow, but must not be silently resolved by changing the agreed experiment. The prior discussion did not record final approval of the complete fixture or permission to run the expanded study.

### Supporting documents and evidence

- [Agreed evaluation plan](TOOL_EVALUATION_PLAN.md): decisions recorded during the design discussion.
- [Proposed organization and case design](TOOL_EVALUATION_CASE_DESIGN.md): detailed boundaries, memberships, and E11-E30 sketches, still proposed.
- [Existing evaluation rules](EVALUATION_RULES.md): independent score definitions, numeric judge rubrics, task metadata mappings, and pilot behavior. The new study preserves these scoring semantics but replaces the pilot's ten-case prompt-round workflow and automatic pass language with the observational comparison described here.
- Existing coordinator, database tools, runner, independent evaluators, telemetry, and offline test suites were inspected to define the interfaces and validation plan. No relevant ADR was present in the repository documentation inspected.
- The saved pilot records confirm fixed model settings and that successful pilot model calls fetched tickets/directories without requesting membership. Dollar costs and asynchronous judge results were not independently verified while writing this specification.

Tracker destination: GitHub Issues in ragtag2/PaperDesk. Intended triage label: ready-for-agent, as required by the invoked to-spec skill. Local preparation and tracker publication are separate completion states; a local document is not evidence that an issue was created.
