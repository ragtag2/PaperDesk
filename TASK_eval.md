# Paperdesk evaluation scope — discussion log

Started: 2026-10-08.

This document preserves user prompts and final assistant answers for the evaluation discussion. Append every subsequent user prompt and final assistant answer in order. Exchanges 1–7 were scope discussion only. In Exchange 8, the user authorized preparing CSV fixtures, expected answers, a seed script and evaluation rules. Running the seed or any project code is not authorized; remaining Langfuse work is user-managed.

The first exchange is the original proposal. Later user decisions supersede earlier proposals, including the original suggestion to use DeepEval.

## Current working scope — updated 2026-10-08

- Purpose: improve team selection, summary quality, and team-reason quality; verify downstream application and active-stakeholder correctness.
- Planned workload: 10 fixed cases and three prompt versions, for 30 complete agent executions.
- Run order: sequential V1 → review → V2 → review → V3. Preserve the current prompt as V1; develop V2 from V1 failures and V3 from V2 failures. This supersedes predefining V2 as rules and V3 as examples.
- Evaluation platform: Langfuse throughout; no DeepEval. Four evaluator categories: team selection, summary quality, reason quality, and application validity.
- Accepted organization: IT Support, Infrastructure, Business Applications, Security & Access, Finance, and Operations.
- Prepared membership: 15 synthetic users in `experiments/users.csv`—12 active team members (two per team), inactive members of IT Support and Finance, and one active user without a team. All IDs and memberships are fixed.
- Prepared coverage: ten cases in `experiments/tickets.csv`—three straightforward, three cross-team, two incomplete-information, one no-relevant-team, and one outdated-coordination case. Nine start without coordination; E10 retains obsolete Security & Access and Finance coordination while its current expected selection is Finance alone. Each row includes a full expected answer, required summary/reason facts and evaluation notes.
- Prepared local setup: `experiments/teams.csv`, `users.csv`, `tickets.csv`, `seed.py`, `requirements.txt`, `EVALUATION_RULES.md` and `README.md`. The seeder always targets a separate `paperdesk_eval` database, upserts stable IDs, restores frozen input state and excludes answer keys from MongoDB. It has not been run. No local experiment runner or prompt revisions were created; the user will perform the remaining Langfuse setup and execution.
- Controls: freeze inputs, expected outcomes, evaluator rubrics and thresholds, agent and judge models/settings, tools, and application code before V1. Only the agent prompt changes across rounds. Prompt examples come from outside the evaluation cases.
- Interpretation: sequential revisions use these cases for development. Results describe performance on this pilot; evaluating unseen-ticket performance would require a later untouched dataset.
- Team terminology: responsible teams handle or fix the ticket issue; affected teams have work or services disrupted by it. These describe reasons for relevance within the existing selected-team list, without requiring new team types or database fields.
- Implementation meaning: an evaluation setup around the existing agent—fixed organization and tickets, answer keys, scoring rules, fixture/seed script, experiment runner, and sequential prompt revisions. An answer key defines expected selections and required facts; a rubric defines scoring criteria.
- Fixture policy and scoring: select responsible and clearly affected teams when supported by current ticket evidence. Deterministic checks cover exact team/stakeholder sets, independently derived active memberships, schema validity and completion. LLM judges assess summaries and team reasons using fixed 0/0.5/1 rubrics; empty-case reason quality is not applicable. Detailed rules and thresholds are in `experiments/EVALUATION_RULES.md`.
- Remaining user-managed work: first commit the existing Langfuse integration on `main`, then create and switch to `feat/agent-evaluation`; experiment files remain uncommitted. Choose/configure judge model and settings, install seed dependencies if needed, seed the database, configure the experiment agent's database and Langfuse dataset/evaluators, then run V1 → review → V2 → review → V3. No seed, agent, evaluator or experiment executions have been performed by this task. The user clarified that commands should be provided as guidance, not executed.
- Authorization: preparation of the requested local files and continuing updates to this log. Do not run the seed or any project code. The user handles the remaining work in Langfuse.

The chronological exchanges below remain the record of user prompts and final assistant answers.


## Exchange 1 — 2026-10-08

### User prompt

okay so we'll devise an experiment. 
we'll create 10 test cases to evaluate different versions of the prompt ( 3 versions ). 
and the evaluators. 
let's define the scope of this , no need to generate anything , let's just dicuss and narrow it down to be realistic

### Assistant answer

I’d frame this as a **small controlled experiment to answer: which prompt selects the correct teams and produces useful, supported summaries and reasons?**

Team selection should be the primary measure. In our agent, Python derives stakeholders from the selected teams, so stakeholder correctness mainly checks that the application still behaves correctly.

**The experiment would contain 10 fixed cases × 3 prompt versions = 30 complete agent executions.** Each execution can contain multiple model and tool calls.

For the three versions, I suggest:

| Version | What we would test |
|---|---|
| V1: baseline | Our current prompt, preserved unchanged |
| V2: explicit rules | Clearer rules for selecting responsible and affected teams, with evidence required for each selection |
| V3: examples | The same rules as V2, plus a small number of examples demonstrating their application |

All three should follow the same business policy. The examples for V3 should come from outside the 10 evaluation cases.

For the **10 cases**, a realistic coverage mix would be:

- **3 straightforward cases:** one clearly relevant team.
- **3 cross-team cases:** several teams have distinct responsibilities or clear business impact.
- **2 incomplete-information cases:** test whether the agent avoids unsupported assumptions.
- **1 case with no relevant team:** an empty selection should be valid.
- **1 updated-ticket case:** previous coordination is outdated and should be reassessed.

These are coverage categories; we would write the actual cases after agreeing on the selection policy.

Each case needs a fixed ticket, team directory, active membership data, and **human-approved expected team IDs**. For summaries and reasons, we should define required facts and acceptable explanations; exact wording should remain flexible. Any ambiguous selection needs an agreed acceptable outcome before testing.

I’d keep the evaluators to these four:

| Evaluator | Method | What it measures |
|---|---|---|
| **Team selection** | Deterministic comparison | Exact team-set match, plus missing and unnecessary teams |
| **Summary quality** | DeepEval judge | Preserves important ticket facts, avoids invented claims, and gives a useful concise summary |
| **Reason quality** | DeepEval judge | Each reason connects ticket evidence to that team’s responsibilities |
| **Application validity** | Deterministic checks | Valid response, known and unique team IDs, correct active stakeholders, successful completion |

DeepEval’s G-Eval supports custom criteria like these and returns scores with explanations. We would keep the judge model and evaluator definitions fixed across all three versions. [G-Eval documentation](https://deepeval.com/docs/metrics-llm-evals)

That means **30 agent executions and 60 text evaluations** for the first pass. An evaluation can require multiple judge-model requests, so those numbers are workload counts, not API-call counts.

To make the comparison fair, we would freeze:

- The test data and expected outcomes.
- The agent model, temperature, tools, and application code.
- The evaluator model, criteria, and scoring thresholds.

Only the agent prompt changes. We should agree on expected outcomes and evaluator criteria **before seeing the results**.

We would run the **full Python agent**, including its database tools and post-processing, through a local experiment runner. Langfuse would hold the three experiment runs, traces, and attached evaluation scores for comparison. That preserves visibility into why a case failed. [Langfuse dataset experiments](https://langfuse.com/docs/evaluation/get-started/offline)

For choosing a winner, I’d prioritize:

1. Correct team selection, including avoiding regressions on important cases.
2. Supported summaries and team reasons.
3. Latency, tokens, and model-call count as secondary tradeoffs.

With 10 cases, one result changes accuracy by 10 percentage points. This is a useful pilot; close results should trigger repeat runs before selecting a winner.

**The first decision to settle is team-selection policy:** should Paperdesk include both the teams responsible for resolving the incident **and clearly affected teams**, or only the resolving teams? Our current prompt includes both. I recommend keeping that policy and requiring concrete evidence for affected-team selections.

## Exchange 2 — 2026-10-08

### User prompt

ok so we use langfuse for everything no deep eval. 
also check if the history of changes to a ticket is saved or not in the db ( to see if it affects our test cases ) 
also, we don't have enough team members and teams so that we can use them for our experiments and such as that we can ( we should define a structure, teams and team members for a good experiment ). 
also create TASK_eval.md
where you save my last two prompts and your answer , then every prompt and answer from here forward. 
don't do anything else aside from task_eval.md 
we're discussing and defining scope

### Assistant answer

Created [TASK_eval.md](C:/Users/rayen/PycharmProjects/ticketSubmission/TASK_eval.md) with your last two prompts, my previous answer, and this answer. I’ll append subsequent prompts and answers there. It is the only file created or changed in this turn.

**We’ll use Langfuse throughout the experiment.** It will hold datasets, prompt versions, experiment results, traces, and evaluation scores. Summary and reason quality will use Langfuse’s LLM-as-a-Judge evaluators, which call a configured judge model. [Langfuse judge documentation](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)

For exact team and stakeholder checks, the simplest initial setup is Python checks in the experiment runner, with scores recorded through the Langfuse SDK. Running code evaluators directly from the self-hosted UI requires an additional evaluator dispatcher. That setup choice remains part of our scope discussion. [Langfuse code evaluators](https://langfuse.com/docs/evaluation/evaluation-methods/code-evaluators)

**The current application does not save a full ticket-edit history.** I checked the database schema and persistence code:

- Ticket edits update the existing document; previous titles, descriptions, priorities, and statuses are not archived. `createdAt` and `updatedAt` are timestamps, not a revision history. [Ticket update code](C:/Users/rayen/PycharmProjects/ticketSubmission/backend/src/modules/tickets/tickets.service.ts:64)
- A successful analysis replaces the ticket’s latest `coordination`; older coordination results are not stored as an array in that ticket. [Coordination save](C:/Users/rayen/PycharmProjects/ticketSubmission/backend/src/modules/tickets/ticketCoordination.ts:7)
- The agent reads the current ticket **including its latest saved coordination**. That previous analysis can therefore influence the next model response. [Agent database reader](C:/Users/rayen/PycharmProjects/ticketSubmission/agents/database.py:44)

For our experiment, I recommend **nine cases with no previous coordination and one case with deliberately outdated coordination**. Each prompt version must receive the same frozen starting state. We should not let V1’s result become V2’s input. The updated-ticket case can test reassessment using a current ticket plus an old coordination result; it does not require a complete edit history.

**For the experimental organization, six teams should be enough:**

| Proposed team | Responsibility boundary |
|---|---|
| IT Support | Employee devices, peripherals, and local software setup |
| Infrastructure | Networks, connectivity, servers, and shared infrastructure |
| Business Applications | Business application defects, configuration, and workflows |
| Security & Access | Authentication systems, access policy, and security incidents |
| Finance | Payments, billing, and payroll processing |
| Operations | Operational scheduling and service delivery |

These are proposed boundaries. Before writing cases, each team needs a clear definition of what it owns, what belongs elsewhere, and when it counts as affected by another team’s incident. That is what makes expected selections defensible.

For membership, I suggest **15 synthetic users**:

- Two active members in each team: **12 users**.
- Two additional inactive members, attached to different teams.
- One active user without a team.

This lets us check that selected teams contribute **all active members**, inactive members are excluded, and unrelated or unassigned users are excluded. The current membership model supports one team per user. More members would mainly expand membership checks; clear team responsibilities matter more for comparing prompts.

The working scope remains **10 cases, three prompt versions, one fixed organization, and four evaluator categories**: team selection, summary quality, reason quality, and application validity. The judge should receive the frozen ticket facts and team responsibilities alongside the output, so it can assess whether the text is supported.

Does this six-team structure match the kind of organization you want Paperdesk to represent?

## Exchange 3 — 2026-10-08

### User prompt

this team structure is okay, so do you have suggestion for how to add them to the db so that we can run the experiment or should we not add them , write here in chat 

### Assistant answer

**I recommend adding them to a separate experiment database, such as `paperdesk_eval`.** It can live in your existing MongoDB Atlas cluster; we would not need another MongoDB server. [MongoDB database documentation](https://www.mongodb.com/docs/manual/core/databases-and-collections/)

This fits our experiment because the agent can exercise its actual database tools against a fixed organization.

Adding the experimental teams to the main Paperdesk database would change what ordinary analyses see: our `list_teams` tool currently retrieves **every team in the selected database**.

The proposed setup would be:

| Location | What it contains |
|---|---|
| Experiment MongoDB database | Six teams, 15 synthetic users, and 10 test tickets |
| Langfuse dataset | Case identifiers, ticket IDs, expected results, and frozen context for evaluators |
| Langfuse experiment runs | Outputs, scores, traces, latency, and token usage for each prompt version |

**To populate MongoDB, I suggest a reproducible seed script rather than entering everything manually.** Later, we would:

1. Define the records in a versioned fixture file, with stable MongoDB IDs and fixed team memberships.
2. Create a small seed script that loads that fixture into `paperdesk_eval` and can restore the same starting state.
3. Configure the experiment runner to use that database. Our agent already supports selecting a database through `MONGODB_DB_NAME`.
4. Run all three prompt versions against the same records.

The runner should call the Python agent directly. The agent reads MongoDB without saving its result there, so outputs can go to Langfuse while the test inputs stay fixed. This also preserves the deliberately outdated coordination in our reassessment case across all three versions.

**Could we avoid adding anything to MongoDB? Yes.** We could make the tools return fixed data from local fixtures. That is useful for testing prompt behavior, but it would bypass the actual MongoDB queries. For our planned experiment, the separate database gives us realistic tool execution with a manageable setup.

Having cases in Langfuse alone would not populate MongoDB—the agent’s database tools still need somewhere to retrieve their records.

My suggested scope is therefore: **one fixed fixture, one seed script, one experiment database, and one runner**, with Langfuse managing the dataset and results. These are proposals for later implementation; this exchange has been appended to [TASK_eval.md](C:/Users/rayen/PycharmProjects/ticketSubmission/TASK_eval.md).

## Exchange 4 — 2026-10-08

### User prompt

okay so should i change to a new branch then make the experiment database , and start the work ? 
answe in chat mode 

### Assistant answer

**Yes—create a new branch before starting the implementation.** I suggest this order:

1. **Save the current Langfuse integration in a commit**, if it isn’t committed yet. That gives us a baseline.
2. **Create a branch**, such as `feat/agent-evaluation`.
3. **Finalize the experiment fixture:** six teams with clear responsibilities, 15 users, and 10 tickets with agreed expected outcomes.
4. **Create and seed `paperdesk_eval`** using a repeatable script with stable IDs.
5. **Build the experiment runner**, add the three prompt versions, and configure the Langfuse evaluators.
6. **Run the 30 analyses**, compare results, and inspect failures before choosing a prompt.

The branch separates **code changes**. The experiment database separates **test data**. Switching branches alone does not change which database the agent uses.

The normal application should keep using its existing database; the experiment runner should explicitly select `paperdesk_eval`.

**The first implementation milestone should be the fixture and seed script.** Once those are ready, we have a stable foundation for the prompts and evaluators.

## Exchange 5 — 2026-10-08

### User prompt

how to turn off the langfuse containers 

### Assistant answer

In PowerShell, run:

```powershell
cd C:\Users\rayen\PycharmProjects\langfuse
docker compose stop
```

This stops all Langfuse containers while keeping their data.

To start them again:

```powershell
docker compose start
```


## Exchange 6 — 2026-10-08

### User prompt

read TASK_eval.md 
there we defined the scope for our eval experiment. re-state what we defined here. 
also i have suggestion , instead of running concurrent experiments with different prompts , how about we run the first , find weaknesses , improve on it then run the second and the third based on that ? 
also update TASK_eval.md from our interactions here 

### Assistant answer

Yes—I recommend **V1 → review → V2 → review → V3**. We keep **10 cases × 3 versions = 30 full agent executions**, while developing each new prompt from the previous version’s weaknesses.

Our current working scope is:

- **Goal:** improve team selection, supported summaries, and useful reasons. Stakeholder checks verify that selected teams contribute the correct active members.
- **Cases:** 10 fixed tickets. The proposed coverage is three straightforward cases, three cross-team cases, two incomplete-information cases, one with no relevant team, and one requiring reassessment of outdated coordination.
- **Organization:** the accepted six teams are IT Support, Infrastructure, Business Applications, Security & Access, Finance, and Operations. Proposed membership remains **15 synthetic users**: two active members per team, two additional inactive members in different teams, and one active user without a team.
- **Evaluation:** four categories—team selection, summary quality, reason quality, and application validity. **Langfuse only; no DeepEval.** Team and stakeholder checks would be deterministic; summaries and reasons would use Langfuse LLM-as-a-Judge evaluators. Langfuse would hold prompt versions, datasets, traces, results, and scores.
- **Data and execution:** the proposed setup is a separate `paperdesk_eval` database, a versioned fixture, a repeatable seed script, and a runner calling the full Python agent with its database tools and post-processing. This setup has been recommended but has not been implemented through this discussion.
- **Ticket history:** the recorded finding is that tickets retain current fields and their latest coordination, without a full revision history. We proposed nine cases without previous coordination and one with deliberately outdated coordination. Every version must receive the same starting state.

For your sequential approach, I suggest:

1. **Run V1:** preserve the current prompt unchanged, evaluate all 10 cases, and inspect scores and traces. Identify specific failures such as missed teams, unnecessary teams, unsupported claims, or weak explanations.
2. **Develop and run V2:** change the prompt to address V1’s observed failures, then rerun all 10 cases. Check both improvements and regressions.
3. **Develop and run V3:** use V2’s remaining weaknesses to guide the next revision, then rerun all 10 cases and compare all three versions.

This replaces the earlier proposal to decide upfront that V2 must add explicit rules and V3 must add examples. Those remain possible techniques; the failures should determine which changes we make.

**Before V1, freeze the inputs, expected outcomes, evaluator criteria and thresholds, agent model/settings, tools, and application code.** Keep them fixed across rounds so that prompt changes explain the differences. The judge model/settings also stay fixed. Examples added to prompts should come from outside the 10 evaluation cases.

Since V2 and V3 learn from this dataset, the results demonstrate improvement on these 10 cases. Measuring performance on unseen tickets would require a separate, untouched dataset later.

Before implementation, we still need to settle the team-selection policy—resolving teams only, or resolving plus clearly affected teams—and approve the expected outcomes and evaluator rubrics. My recommendation remains to include resolving and clearly affected teams when ticket evidence supports them.

Updated [TASK_eval.md](C:/Users/rayen/PycharmProjects/ticketSubmission/TASK_eval.md) with the current scope, your sequential proposal, and this exchange. Only that document was changed; implementation remains outside this discussion.


## Exchange 7 — 2026-10-08

### User prompt

Before implementation, we still need to settle the team-selection policy—resolving teams only, or resolving plus clearly affected teams—and approve the expected outcomes and evaluator rubrics. My recommendation remains to include resolving and clearly affected teams when ticket evidence supports them., what do you mean resolve teams ? what are we implementing and what do we need ?

### Assistant answer

By **“resolving teams,” I mean teams responsible for fixing or handling the ticket’s issue**. “Responsible teams” is clearer wording.

For example, suppose a network outage prevents Finance from processing payroll:

| Team | Why it is relevant |
|---|---|
| Infrastructure | Responsible for restoring network connectivity |
| Finance | Affected because its payroll work is blocked |

My suggestion is to select **both**, because the ticket provides a concrete reason to involve each team.

Your [current agent prompt](C:/Users/rayen/PycharmProjects/ticketSubmission/agents/agent.py:26) already considers teams responsible for handling an issue and teams potentially affected by it. We need to make that rule precise enough to judge whether a selection is correct. These are descriptions of why a team is relevant; they do not require new team types or database fields.

**We are planning to implement an evaluation setup around your existing agent.** Its purpose is to measure whether prompt changes improve its decisions, summaries, and explanations.

We need these pieces:

1. **Fixed experiment data:** the six teams with clear responsibilities, the proposed 15 users, and 10 tickets. A fixture file would define these records; a seed script would load them into the separate `paperdesk_eval` database.
2. **An answer key for each ticket:** the teams we expect the agent to select, the important facts its summary should preserve, and the evidence its team reasons should mention. Expected stakeholders follow from the selected teams’ active members.
3. **Evaluation rules:** exact checks for selected teams and stakeholders; judge criteria for summaries and reasons; checks that the output is valid and the execution succeeds. A “rubric” simply means these scoring rules—for example, “the summary preserves the main issue and impact without inventing facts.”
4. **An experiment runner:** a small program that runs the agent on all 10 tickets using one prompt version, checks its output, and records results, traces, and scores in Langfuse.
5. **Sequential prompt revisions:** run the current prompt as V1, inspect weaknesses, develop and run V2, then develop and run V3. Each round uses the same data and scoring rules.

When I said **“approve expected outcomes,”** I meant agreeing on the answer key before seeing the agent’s results. Otherwise, we would be scoring it without a clear definition of a correct answer.

The first concrete milestone would be **defining the teams’ responsibilities and the 10 tickets’ expected outcomes**, then preparing the fixture and seed script. V2 and V3 come after we inspect earlier results.

I’ve added this clarification and our exchange to [TASK_eval.md](C:/Users/rayen/PycharmProjects/ticketSubmission/TASK_eval.md). We remain in scope discussion; only that document was changed.


## Exchange 8 — 2026-10-08

### User prompt

okay the 6 teams you devized are okay , so let's create a folder called experiments where we put the structure of the teams in a csv file. 
the the proposed users in a csv file 
and the 10 tickets in a csv file 
then we define the seed script that will insert them 
in the tickets csv put the expected answer.
then in a .md put the evaluation rules , the parts we use llm as a judge for and the deterministic parts. 

don't run the seed code or any code 

then give me commands to create the branch for experiments 
everything else i will do myself on langfuse 

### Assistant answer

Created `experiments/` with:

- [teams.csv](C:/Users/rayen/PycharmProjects/ticketSubmission/experiments/teams.csv): six teams and responsibility boundaries.
- [users.csv](C:/Users/rayen/PycharmProjects/ticketSubmission/experiments/users.csv): 15 users with fixed IDs, memberships, and active/inactive states.
- [tickets.csv](C:/Users/rayen/PycharmProjects/ticketSubmission/experiments/tickets.csv): 10 cases with expected teams, stakeholders, example summaries/reasons, and required facts.
- [seed.py](C:/Users/rayen/PycharmProjects/ticketSubmission/experiments/seed.py): loads the records into `paperdesk_eval` using fixed-ID upserts. Expected answers stay outside MongoDB.
- [EVALUATION_RULES.md](C:/Users/rayen/PycharmProjects/ticketSubmission/experiments/EVALUATION_RULES.md): deterministic checks and LLM judge rubrics.
- [README.md](C:/Users/rayen/PycharmProjects/ticketSubmission/experiments/README.md): case overview, dependencies, and manual seed instructions.

Updated `TASK_eval.md` and the work log. **Static review only: no seed, tests, installations, database writes, or Langfuse operations were run.**

To create the branch, run:

```powershell
Set-Location "C:\Users\rayen\PycharmProjects\ticketSubmission"
git switch -c feat/agent-evaluation
```


## Exchange 9 — 2026-10-08

### User prompt

no i meant , commit the langfuse changes , then switch to a branch 

### Follow-up user prompt

guide me , don't execute commands

### Assistant answer

From the project root, run these in order:

```powershell
git add -- agents
git commit -m "Add Langfuse tracing for incident analysis"
git switch -c feat/agent-evaluation
```

This commits the Langfuse changes on `main`, then creates and switches to the experiment branch. Your `experiments/` files remain uncommitted and available on the new branch.


## Exchange 10 — 2026-10-08

### User prompt

okay now then what's next 

### Assistant answer

On your experiment branch, first save the prepared files:

```powershell
git add -- experiments TASK_eval.md
git commit -m "Add evaluation fixtures and seed script"
```

Then install the seed dependencies and populate the experiment database:

```powershell
.\agents\.venv\Scripts\python.exe -m pip install -r .\experiments\requirements.txt
.\agents\.venv\Scripts\python.exe .\experiments\seed.py
```

The script reads the MongoDB connection from `agents/.env` and targets `paperdesk_eval`. Expected success output:

```text
Seeded 6 teams, 15 users and 10 tickets in paperdesk_eval.
```

After that, prepare your Langfuse dataset and evaluators:

- **Dataset:** 10 items from `tickets.csv`; each input is `{"ticketId": "..."}`, with the parsed `expected_answer_json` as its reference output.
- **Evaluator context:** include the frozen ticket facts, team responsibilities, required facts, and evaluation notes.
- **Scoring:** follow `experiments/EVALUATION_RULES.md`.
- **Agent configuration:** explicitly use `MONGODB_DB_NAME=paperdesk_eval` for the experiment agent.

Each case should invoke the full Python agent, including its database tools and stakeholder assembly. Once the dataset and evaluators are ready, run **V1 only**, inspect its weaknesses, then develop V2.
