# Paperdesk API

Express, TypeScript, and MongoDB backend for the Paperdesk MVP. The routes and data shapes follow the project-root `API_CONTRACT.md`.

## Local setup

1. Run `npm install` in `backend/`.
2. Copy `.env.example` to `.env`, set the Atlas URI and a random `SESSION_SECRET` (32+ characters). The database defaults to `paperdesk`; change `MONGODB_DB_NAME` if needed. Set `FRONTEND_ORIGIN` to the exact frontend origin.
3. Run `npm run dev`. The API listens on port 3000 by default.
4. Set `ADMIN_NAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` in your environment and run `npm run seed:admin` once to create the first admin. Public sign-up creates employees only.
5. In `frontend/.env.local`, set `VITE_API_BASE_URL=http://localhost:3000` and `VITE_DEMO_MODE=false`.

If Windows reports `querySrv ECONNREFUSED` for the Atlas URI, set `MONGODB_DNS_SERVERS=1.1.1.1,8.8.8.8` in `backend/.env`. This applies only to `mongodb+srv://` connections in the backend process; omit it on hosts with working DNS.

Run `npm run build` for a TypeScript check and emitted JavaScript. The API tests use a disposable local MongoDB instance on port 27018:

```sh
docker run --rm -d --name paperdesk-api-test-mongo -p 127.0.0.1:27018:27017 mongo:8.0
npm test
docker stop paperdesk-api-test-mongo
```

## Incident coordination

Admins can create, list, and update teams at `/teams`, and assign members with
`teamId` through the existing admin user endpoints. Tickets expose a nullable
`coordination` result containing the summary, relevant teams, stakeholders, and
analysis date.

Start the Python service following `../agents/README.md`, then set
`AGENT_BASE_URL=http://127.0.0.1:8000` in the backend environment and restart the
API. Both services must use the same MongoDB database. The backend sends only a
ticket ID; the Python agent retrieves its context directly from MongoDB.

Ticket creation and edits trigger analysis in the background. Failures leave the
ticket usable and preserve previous coordination; old analyses cannot overwrite
an edited ticket. Without `AGENT_BASE_URL`, automatic analysis is disabled. The
MVP uses in-process tasks rather than a persistent queue.

To analyze an existing ticket and store its coordination result through the same
backend client and conditional save used by automatic analysis, run from `backend/`:

```powershell
npm.cmd run agent:analyze -- <existing-ticket-id>
```

The command requires the configured MongoDB connection and a running Python
agent. It writes only the ticket's `coordination`, preserves `updatedAt`, and
reports whether the returned summary, teams, reasons, and stakeholders were
saved correctly. It also resolves the same display names used by ticket API
responses and saves a local `*-saved.json` report in
`../agents/runs/analyses/<ticketId>/`. The Python service also saves its full
analysis report there for both this command and automatic backend calls. If the
ticket is edited while the model is running, the conditional save preserves the newer
ticket and the command reports that the analysis was not saved. This is a local
operator command using database credentials, separate from browser login.

## Notifications

`GET /notifications`, `PATCH /notifications/:id/read`, and
`PATCH /notifications/read-all` use the existing session authentication and
operate only on the current recipient's records. List responses include
pagination and a global `unreadCount`; `unread=true` filters unread entries.
Notifications are stored in the `notifications` collection with indexes for
recipient/date, recipient/read status, and a unique event key.

The coordination save atomically retrieves its previous value and creates
alerts for newly added active stakeholders only after the save succeeds.
Unchanged or stale analyses produce no duplicate alerts. A ticket transition
to resolved alerts its active creator and current active stakeholders; repeating
that status does not produce another event. Existing coordination is not
backfilled with notifications. Notification writes are best effort with logging
on failure and no durable delivery queue.

Employees now read their own tickets and tickets listing them as stakeholders.
`GET /tickets?involvingMe=true` filters by stakeholder membership for every role;
the existing edit/delete permissions remain separate. Notification history is
retained after deletion/removal from involvement, with `ticketAvailable=false`.
The frontend reads these endpoints every 30 seconds while visible without
calling the agent. Full field definitions and event rules are in
`../API_CONTRACT.md`.

## Deployment

Run the API behind HTTPS with `FRONTEND_ORIGIN` set to the public frontend origin. Set `TRUST_PROXY=1` when the app is behind one trusted ingress proxy so secure cookies follow the forwarded HTTPS request. Keep `MONGODB_URI` and `SESSION_SECRET` in deployment secrets. The MongoDB Atlas database runs off the Raspberry Pi; the frontend and API can run in k3s.
