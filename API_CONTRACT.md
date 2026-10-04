# Paperdesk API contract (v1)

Backend handoff for the React app in `frontend/`. Keep this contract, the backend, and `frontend/src/api/types.ts` / `frontend/src/api/client.ts` aligned when API behavior changes.

## Transport and authentication

- API base URL: `VITE_API_BASE_URL`, without an `/api` prefix. Local default: `http://localhost:3000`; frontend: `http://localhost:5173`.
- Send JSON bodies with `Content-Type: application/json`. Success responses are JSON except `204 No Content`, which has no body.
- Use an opaque server-side session cookie named `paperdesk.sid`. Login sets it; logout invalidates the session and clears it. The frontend uses `credentials: "include"` and fetches `/users/me` after login and on reload. Do not return a bearer token or session ID in JSON.
- Cookie attributes: `HttpOnly; SameSite=Lax; Path=/`, plus `Secure` on HTTPS. Expired, revoked, and deactivated-user sessions return `401`.
- If frontend and API origins differ, set `Access-Control-Allow-Origin` to the exact frontend origin, `Access-Control-Allow-Credentials: true`, and `Vary: Origin`; allow `Content-Type` on preflight. Reject untrusted `Origin` values on browser `POST`, `PATCH`, and `DELETE` requests. Serve both from the same site in production; a cross-site deployment needs a separate cookie and CSRF decision.

## Data shapes

IDs are MongoDB ObjectId strings (`_id`, not `id`); dates are UTC ISO 8601 strings. List items and detail responses use the same shapes.

| Type | Required fields |
| --- | --- |
| `User` | `_id`, `name`, `email`, `role`, `isActive`, `teamId`, `createdAt`, `updatedAt` |
| `Team` | `_id`, `name`, `responsibilities`, `createdAt`, `updatedAt` |
| `Ticket` | `_id`, `title`, `description`, `category`, `priority`, `status`, `creatorId`, `assigneeId`, `creator`, `assignee`, `coordination`, `createdAt`, `updatedAt` |
| `TicketCoordination` | `summary`, `relevantTeams: { teamId, name, reason }[]`, `stakeholderUserIds: string[]`, `stakeholders: Assignee[]`, `analyzedAt` |
| `Assignee` | `_id`, `name` |
| `Page<T>` | `items: T[]`, `page: number`, `limit: number`, `total: number` |
| `Notification` | `_id`, `userId`, `ticketId`, `ticketTitle`, `type`, `createdAt`, `readAt`, `ticketAvailable` |
| `NotificationPage` | `Page<Notification>` fields plus `unreadCount: number` |

`User.role`: `employee | support | admin`; `isActive` is boolean. `Ticket.category`: `hardware | software | network | other`; `priority`: `low | medium | high`; `status`: `open | in_progress | resolved`. `creatorId` is a string; `assigneeId` is a string or `null`. Every ticket includes `creator: Assignee` and `assignee: Assignee | null`. Never return passwords or password hashes.

`User.teamId` is a team ObjectId string or `null`; each user belongs to at most
one team. `Ticket.coordination` is `TicketCoordination | null`, initially `null`.
Coordination IDs are ObjectId strings and `analyzedAt` is a UTC ISO date.
Express enriches the stored result with each relevant team's current `name`
(`string | null`, null if unavailable) and `stakeholders` containing the IDs and
current names of available users from `stakeholderUserIds`. These display fields
are included for anyone permitted to read the ticket; the teams and users
management endpoints remain admin-only. The agent response below contains IDs
and reasons; Express supplies display names when reading tickets.

## Endpoints

`Auth` means any active signed-in user. `Staff` means support or admin. `Owner` means the ticket's creator. `Stakeholder` means a user listed in the ticket's latest saved `coordination.stakeholderUserIds`. A body shown as `—` means no request body; a `204` response has no body.

| Method and path | Access | Body or query | Success |
| --- | --- | --- | --- |
| `POST /auth/signup` | Public | Body: `name`, `email`, `password` | `201 User`; create active employee, no automatic login |
| `POST /auth/login` | Public | Body: `email`, `password` | `204`; set session cookie; only active users can log in |
| `POST /auth/logout` | Auth | — | `204`; revoke session and expire cookie |
| `GET /users/me` | Auth | — | `200 User` |
| `PATCH /users/me` | Auth | Body: nonempty subset of `name`, `email` | `200 User` |
| `PATCH /users/me/password` | Auth | Body: `currentPassword`, `newPassword` | `204`; verify current password, retain current session |
| `GET /users` | Admin | Query: `page`, `limit`, `role`, `isActive`, `teamId` | `200 Page<User>`; includes inactive users |
| `POST /users` | Admin | Body: `name`, `email`, `password`, `role`; optional `teamId` | `201 User`; create active user |
| `GET /users/:id` | Admin | — | `200 User`; includes inactive user |
| `PATCH /users/:id` | Admin | Body: nonempty subset of `name`, `email`, `role`, `isActive`, `teamId` | `200 User`; `isActive: true` reactivates |
| `POST /teams` | Admin | Body: `name`, `responsibilities` | `201 Team` |
| `GET /teams` | Admin | No query parameters | `200 Team[]`; sort by name, then `_id`, ascending |
| `PATCH /teams/:id` | Admin | Body: nonempty subset of `name`, `responsibilities` | `200 Team` |
| `DELETE /users/:id` | Admin | — | `204`; deactivate, preserve record/tickets, revoke sessions; repeat is allowed |
| `GET /tickets/assignees` | Staff | — | `200 Assignee[]`; active support/admin users only |
| `GET /tickets` | Auth | Query: `page`, `limit`, `status`, `priority`, `category`, `assigneeId`, `involvingMe` | `200 Page<Ticket>`; employees see own and stakeholder tickets; `assigneeId` is staff-only |
| `POST /tickets` | Auth | Body: `title`, `description`, `category` | `201 Ticket`; derive `creatorId` from session; default `priority=medium`, `status=open`, `assigneeId=null` |
| `GET /tickets/:id` | Owner, stakeholder, or staff | — | `200 Ticket` |
| `PATCH /tickets/:id` | Per field rules below | Body: nonempty subset of `title`, `description`, `category`, `priority`, `status`, `assigneeId` | `200 Ticket` |
| `DELETE /tickets/:id` | Owner while open, or admin | — | `204`; remove ticket |
| `GET /notifications` | Auth, own notifications only | Query: `page`, `limit`, `unread` | `200 NotificationPage` |
| `PATCH /notifications/read-all` | Auth, own notifications only | — (empty object also accepted) | `204`; mark notifications existing at request time as read |
| `PATCH /notifications/:id/read` | Auth, notification recipient | — (empty object also accepted) | `200 Notification`; idempotently mark as read; hidden/missing ID returns `404` |

## Permissions and validation

| Ticket action | Employee | Support | Admin |
| --- | --- | --- | --- |
| Read/list | Own or current stakeholder | All | All |
| Edit `title`, `description`, `category` | Own, while open | Own, while open | Any |
| Edit `priority`, `status`, `assigneeId` | Never | Any | Any |
| Delete | Own, while open | Own, while open | Any |

- Enforce ticket visibility on list and detail queries. Stakeholder access grants reading only; editing/deleting still follows the existing owner/staff rules. Return `404` for a ticket that does not exist or is not visible; return `403` for a forbidden change to a visible ticket. A patch succeeds only when every field is permitted.
- Trim names, ticket titles, and descriptions; require nonempty values. Title limit: 120 characters; description limit: 5,000. Normalize emails to lowercase, require valid unique addresses, and require passwords of at least 8 characters.
- `assigneeId` accepts `null` or the ID of an active support/admin user. Staff can move a ticket between any defined statuses. Reject unknown body fields and invalid enum values.
- Admins cannot deactivate themselves or change their own role away from admin. Admin user updates cannot change another user's password. Wrong `currentPassword` returns `400`.
- Only admin user creation and editing accept `teamId`; it must be `null` or an
  existing team's ID. Omitted membership defaults to `null` on creation.
  Public signup creates users with `teamId=null`; profile editing cannot change
  membership. No separate membership collection is used.
- Team names and responsibilities are trimmed and nonempty, with limits of 120
  and 5,000 characters respectively. Unknown fields and empty patches return
  `400`. A missing team on `PATCH /teams/:id` returns `404`.
- Clients cannot write `coordination` through ticket creation or patching.
- `GET /tickets?involvingMe=true` limits results to tickets whose latest saved
  coordination includes the authenticated user as a stakeholder, for every role.
  `false` or an omitted parameter uses ordinary ticket visibility. Other values
  return `400`; this filter combines with status, priority, category, and assignee
  filters before pagination and counts.
- `GET /users` accepts `teamId` as a team ObjectId or `none` for users without
  a team (null or missing membership). Omit it for all teams. Team, role, and
  active-status filters combine before counting and pagination. The Teams UI
  lists available members with `teamId=none&isActive=true` and assigns selected
  people using the existing admin `PATCH /users/:id` with `{ teamId }`.
- For lists, `page` and `limit` are positive integers (defaults `1` and `10`; maximum limit `100`). `isActive` accepts `true` or `false`; other filters use the enum values or a valid `assigneeId`. Reject invalid or unknown query parameters. `total` is after access rules and filters, before pagination. Sort by `createdAt` descending, then `_id` descending. An out-of-range page has empty `items` and retains the requested `page`.

## Errors

Every error is JSON with exactly `{ "message": string }`. Use `400` for invalid input or ID format, `401` for missing/expired session or invalid login, `403` for forbidden access, `404` for missing/invisible records, `409` for an email conflict, and `500` for unexpected errors without exposing internal details. Invalid login and inactive account use the same `401` message.

## Ticket notifications

Notifications are persisted in MongoDB's `notifications` collection and are
available only to their recipient, including for support/admin users. IDs and
timestamps follow the shared conventions. `type` is `ticket_involvement` or
`ticket_resolved`; `readAt` is a UTC ISO string or `null`. `ticketTitle` is the
title at notification creation. `ticketAvailable` is computed from current
ticket existence and the recipient's current read permissions. History remains
readable after ticket deletion or removal from the stakeholder list, with
`ticketAvailable=false` and no active ticket link in the frontend.

`GET /notifications` has the shared pagination defaults/cap and newest-first
ordering. Omitted `unread` includes all notifications; `true` includes unread
only and `false` includes read only. Other values and unknown query fields return
`400`. `total` follows the filter; `unreadCount` counts all unread notifications
for that recipient, independent of pagination/filter. Read operations accept no
body or `{}`; reject other body fields. No endpoint accepts a recipient ID from
the caller, and repeating a read operation preserves its original `readAt`.

After a successful conditional coordination save, newly added active stakeholders
receive involvement alerts. Failed or stale analyses create no alerts. An atomic
read of the previous coordination determines additions; an indexed event key
allows at most one involvement alert per recipient/ticket edit revision. Reanalysis
with unchanged stakeholders stays quiet. Existing analyses are not backfilled.
When a saved ticket changes from another status to `resolved`, active stakeholders
and the active creator receive resolution alerts. Repeating a resolved patch does
not create another resolution event. A later reopen/resolution creates a new event.

Notification writes are best effort after ticket/coordination persistence; a
write failure is logged and does not fail the ticket operation. The MVP has no
durable notification queue or automatic delivery retry. The frontend refreshes
recent notifications and unread counts every 30 seconds while visible, on window
focus, and when opening the bell. Notification reads invoke no model calls.

## Incident coordination agent MVP (separate Python service)

The FastAPI service in `agents/` has its own base URL, locally
`http://127.0.0.1:8000`. Its endpoint is an internal service operation, separate
from the Express endpoints and browser session authentication above. The local
service binds to loopback; the frontend continues to use Express.

| Method and path | Access | Body | Success |
| --- | --- | --- | --- |
| `POST /analyze-ticket` | Internal local caller | `{ "ticketId": ObjectId string }` | `200 CoordinationResult` |

Only `ticketId` is accepted in the request. The Python agent reads the ticket,
teams, and members directly from MongoDB using `get_ticket`, `list_teams`, and
`get_team_members`. Express does not supply team or member context.

### Coordination result

| Field | Type and meaning |
| --- | --- |
| `ticketId` | ObjectId string identifying the analyzed ticket |
| `summary` | Nonempty string summarizing the incident |
| `relevantTeams` | Array of `{ teamId: ObjectId string, reason: nonempty string }`; responsible or potentially affected teams |
| `stakeholderUserIds` | Array of ObjectId strings for all active members of the selected teams |

Each ticket acts as one incident. Repeating the request reads current data and
returns a fresh result. LangChain chooses relevant teams with reasons; Python
retrieves their members to assemble the stakeholder set.

The agent writes a local debug report for every valid ticket analysis under
`agents/runs/analyses/<ticketId>/`, including failed requests. Reports retain
team reasons, result checks, timing, and model/tool/token metrics. This does not
change the HTTP result schema. The frontend displays relevant team names without
their debugging reasons; reasons remain in stored coordination and local reports.

### Agent database expectations

- `tickets` uses the existing fields. The agent also reads an optional
  `coordination` field if a previous result has been stored.
- `teams` contains `_id: ObjectId`, `name: string`, and
  `responsibilities: string`.
- Existing `users` records can have `teamId: ObjectId` linking them to one team.
  The member tool selects users with `isActive: true` and returns only `_id`,
  `name`, and `teamId`.

Express manages teams and memberships through the endpoints above. The agent
service reads data and returns its result without database writes.

### Backend integration

Set optional `AGENT_BASE_URL` in the backend environment to enable coordination
(locally `http://127.0.0.1:8000`). When it is unset or empty, ticket operations
continue without invoking the agent.

After each successful ticket creation or patch, Express sends only `{ ticketId }`
to `POST /analyze-ticket` in the background, with a 60-second request timeout.
Ticket requests do not wait for the analysis. The backend validates the returned
result and stores `Ticket.coordination`, adding `analyzedAt`.

The save matches the ticket's `updatedAt` from the triggering operation, so an
analysis for an older edit cannot replace a newer result. Saving coordination
does not change ticket `updatedAt`; `analyzedAt` records that background update.
Failed calls retain the previous coordination result and do not fail the ticket
request. Ticket list and detail responses include the latest stored result.
The MVP runs these tasks in the backend process without a queue or automatic
retries. Team and membership changes are picked up on the next ticket analysis.

### Agent errors

Errors from `POST /analyze-ticket` use `{ "message": string }`: `400` for an
invalid body or ticket ID, `404` for a missing ticket, `503` when MongoDB is
unavailable, and `502` when the model cannot produce a valid analysis.

See `agents/README.md` for the MVP explanation, setup, and examples.
