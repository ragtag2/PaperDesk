# Incident coordination agent MVP

A standalone Python service using FastAPI and LangChain. It reads a ticket,
identifies teams responsible for handling it or affected by it, and returns the
people who should be involved.

Each ticket acts as one incident. Calling the endpoint again after editing a
ticket produces a fresh coordination result.

## Teams, members, and stakeholders

- A **team** has a name and a plain-text description of its responsibilities.
- A **member** is an existing user whose `teamId` points to a team. A user belongs
  to one team in this MVP; there is no separate membership collection.
- A **stakeholder** is a member of a team relevant to a particular ticket. The MVP
  includes all active members of the selected teams.

For example, a payroll application outage could involve IT because it maintains
the application, and Finance because it cannot process payroll.

## Input and output

FastAPI exposes `POST /analyze-ticket`. The caller supplies only:

```json
{ "ticketId": "507f1f77bcf86cd799439011" }
```

The agent retrieves context directly from MongoDB through three LangChain tools:

| Tool | Reads |
| --- | --- |
| `get_ticket(ticket_id)` | Ticket details and any existing `coordination` result |
| `list_teams()` | Team IDs, names, and responsibilities |
| `get_team_members(team_id)` | Active users belonging to a team |

LangChain selects relevant teams and supplies a summary and reasons. Python then
uses the member tool to build the stakeholder list from the selected teams.

Example response:

```json
{
  "ticketId": "507f1f77bcf86cd799439011",
  "summary": "Finance cannot access the payroll application.",
  "relevantTeams": [
    {
      "teamId": "507f1f77bcf86cd799439012",
      "reason": "IT maintains the payroll application."
    }
  ],
  "stakeholderUserIds": ["507f1f77bcf86cd799439013"]
}
```

The tools read the database; the service returns the result without saving it.
Express triggers analysis after creating or editing a ticket when its
`AGENT_BASE_URL` is configured, then saves the returned result on the ticket as
`coordination`. Ticket requests return without waiting for the model.

## Database data

Use the same MongoDB database as Paperdesk:

- `tickets`: the existing collection.
- `teams`: documents with `_id: ObjectId`, `name: string`, and
  `responsibilities: string`.
- `users`: the existing collection, with a `teamId: ObjectId` field for members.

Example team document, using MongoDB shell notation:

```javascript
{
  _id: ObjectId("507f1f77bcf86cd799439012"),
  name: "IT",
  responsibilities: "Maintains internal applications and network infrastructure."
}
```

Populate teams through the admin-only Express `POST /teams` endpoint, and assign
members through `POST /users` or `PATCH /users/:id` with `teamId`. Express also
provides `GET /teams` and `PATCH /teams/:id`. The Python service does not seed or
update database records. The frontend Teams and Users screens manage the directory
and team membership.

Organization data is stored in MongoDB and retrieved for each analysis. The MVP
does not search historical incidents or use a separate memory system. If a
ticket already has a `coordination` field, the ticket tool includes it as context.

## Structure

```text
agents/
  main.py          FastAPI endpoint and service lifecycle
  agent.py         LangChain agent and stakeholder assembly
  tools.py         Three database tools
  database.py      MongoDB reads and serialization
  schemas.py       Request and response models
  config.py        Environment settings
  model.py         Provider initialization and model request limits
  reporting.py     Per-analysis JSON reports and per-model request metrics
  scripts/
    check_connections.py  Check MongoDB and Groq model availability
    run_live.py           Start FastAPI and analyze an existing ticket over HTTP
  runs/
    *-agent-stdout.log / *-agent-stderr.log  Local service output (ignored)
    analyses/<ticketId>/  Timestamped analysis and live-check reports (ignored)
```

## Run locally

Requires Python 3.11 or newer. From the project root, using PowerShell:

```powershell
python -m venv agents/.venv
agents/.venv/Scripts/python.exe -m pip install -r agents/requirements.txt
```

If `agents/.env` does not exist yet, copy `agents/.env.example` into it. Keep
existing credentials when updating a configured environment.

Set the same MongoDB connection and database name as Express, and configure Groq:

```dotenv
AGENT_MODEL=groq:qwen/qwen3.8-27b
GROQ_API_KEY=your-groq-api-key
AGENT_MODEL_TIMEOUT_SECONDS=20
AGENT_MODEL_MAX_TOKENS=2048
```

The included `langchain-groq` adapter initializes `ChatGroq`. The display name
`groq:Qwen/Qwen3.8-27B` is also accepted and normalized to Groq's lowercase API ID.
Qwen reasoning is disabled for this concise coordination workflow. Each model
call has a configured timeout and output limit, with automatic provider retries
disabled; the existing graph recursion limit is 20. A per-call timeout is not a
deadline for the whole analysis. Express retains its 60-second HTTP timeout.

For Atlas SRV lookup issues, Python also honors
`MONGODB_DNS_SERVERS=1.1.1.1,8.8.8.8`, matching the backend setting. Credentials
remain in the agent environment; startup errors identify missing settings.

```powershell
agents/.venv/Scripts/python.exe -m uvicorn agents.main:app --host 127.0.0.1 --port 8000
```

This is an internal local service, separate from Express. Its interactive API
documentation is at `http://127.0.0.1:8000/docs`.

Every valid ticket analysis automatically creates
`agents/runs/analyses/<ticketId>/<timestamp>-<analysisId>.json`, including calls
from Express. A running report is atomically replaced with `passed` or `failed`
when analysis finishes. Reports include model, ticket title, team count, timing,
HTTP status, the complete result (including team reasons), and consistency
checks. Metrics include model call counts, requested tools, actual database tool
calls, input/output/cached input tokens, and each model request's timing/status.
Failed requests retain the usage recorded before failure and a redacted error;
missing tickets produce reports with HTTP 404 without invoking Groq. The checks
confirm structural consistency, not the semantic quality of the team selection.
Interrupted processes can leave a report marked `running`.

Report writes are best effort: a filesystem error is logged without discarding
an otherwise valid result. Reports are local debug files, not browser-visible
content or MongoDB records. The interface displays team names and stakeholders;
team reasons stay available in reports and the stored coordination payload.
Service stdout/stderr stay separate from per-ticket reports. Local process
metadata and backend/frontend process output live in the ignored `.runtime/`
directory.

To enable automatic coordination, also set
`AGENT_BASE_URL=http://127.0.0.1:8000` in `backend/.env` and restart Express. Both
services must use the same MongoDB database. Failed analyses preserve any
previous result; changes to teams and memberships are used on the next analysis.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analyze-ticket -ContentType application/json -Body '{"ticketId":"507f1f77bcf86cd799439011"}'
```

## Live checks

Check MongoDB access and whether Groq lists the selected model for your key:

```powershell
agents/.venv/Scripts/python.exe -m agents.scripts.check_connections
```

This prints only connection status and record counts, and sends no database
records to Groq.

Run an actual analysis through HTTP using the latest existing MongoDB ticket:

```powershell
agents/.venv/Scripts/python.exe -m agents.scripts.run_live
```

Or choose a specific existing ticket:

```powershell
agents/.venv/Scripts/python.exe -m agents.scripts.run_live --ticket-id 507f1f77bcf86cd799439011
```

The runner starts a local FastAPI subprocess, waits for its API to become ready,
sends only `{ ticketId }` to `/analyze-ticket`, and prints the real response. The
agent reads the ticket and team context from MongoDB and sends tool results to
Groq. It validates the response schema, ticket identity, known/unique teams, and
the exact union of active team members. It saves a timestamped `*-live.json`
report and service log in `agents/runs/analyses/<ticketId>/`, then stops only the
service it started. Neither the runner nor the agent writes MongoDB records.
Model call counts, tool names,
token usage, and analysis timing are included when the runner starts the service.
The agent's automatic report includes those metrics for running-service calls too.

If the agent is already running, use `--use-running-agent`. A separate temporary
service can use `--port 8001`. The running-service option uses that service's
model settings; the report's configured model is read from the runner environment.

These checks establish real connectivity and data consistency. Assess routing
quality by reviewing the reasons against your teams' responsibilities and
running multiple tickets. Empty team/member lists can be valid; the runner does
not infer whether a team selection is semantically correct.

For application integration, keep Express running with `AGENT_BASE_URL` set,
create or edit a ticket, then read `GET /tickets/:id` until a fresh
`coordination.analyzedAt` appears. Direct agent calls return an analysis without
saving it; Express performs the background save. The runner does not invoke
Express's persistence path.

To verify persistence on an existing ticket without editing its content, use
`npm.cmd run agent:analyze -- <existing-ticket-id>` from `backend/` while the
Python service is running. This calls the real agent over HTTP, stores the
returned coordination through Express's existing save function, and verifies
the saved fields and display names. See `../backend/README.md`.

Implementation references: [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents),
[structured output](https://docs.langchain.com/oss/python/langchain/structured-output),
[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), and
[Groq integration](https://docs.langchain.com/oss/python/integrations/chat/groq),
[Groq models](https://console.groq.com/docs/models), and
[Groq reasoning settings](https://console.groq.com/docs/reasoning).
