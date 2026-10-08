# Agent evaluation fixtures

Prepared: 2026-10-08.

This folder contains the requested local experiment data, a seed script and
evaluation rules. The files were prepared without executing the seed script,
tests, dependency installation, agent analyses or Langfuse operations.

## Files

| File | Contents |
| --- | --- |
| `teams.csv` | Six teams with explicit responsibility boundaries. |
| `users.csv` | Fifteen synthetic users: twelve active team members, two inactive members in different teams, and one active unassigned user. |
| `tickets.csv` | Ten tickets with reference answers, required facts and evaluation notes. |
| `seed.py` | Manually invoked loader for the fixed `paperdesk_eval` database. |
| `requirements.txt` | Python dependencies for the seed script. |
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

These commands are provided for you to run later. They have not been executed.
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
run it, then develop and run V3. Remaining Langfuse configuration and execution
are yours to manage; this folder contains no experiment runner or prompt revisions.

## Branch command

From the project root:

```powershell
git switch -c feat/agent-evaluation
```
