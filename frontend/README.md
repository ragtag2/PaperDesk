# Paperdesk frontend

React and TypeScript frontend for the ticket submission app described in [`../mvp.docx`](../mvp.docx). It includes public authentication pages, a ticket dashboard and details, a create-ticket form, profile settings, and admin user and team management.

## Run locally

From this `frontend/` directory, use Node.js 20.19+ (Node.js 24 was used during development).

```sh
npm install
npm run dev
```

In Windows PowerShell, use `npm.cmd` in place of `npm` if script execution is disabled.

Open the local URL printed by Vite. With no API URL configured, development mode opens a clearly labeled sample workspace. Choose Ava (employee), Mia (support), or Sam (admin) on the login page; each sample account uses `password123`. Sample changes are stored in your browser's local storage. This mode is for reviewing the frontend and is disabled in production builds.

To use an Express backend, create `.env.local` from `.env.example` and set:

```env
VITE_API_BASE_URL=http://localhost:3000
VITE_DEMO_MODE=false
```

The [API contract](../API_CONTRACT.md) uses a server-side session cookie. The API client sends cookies with requests. If the backend runs on another origin, set its `FRONTEND_ORIGIN` to the exact frontend origin.

## API expectations

The typed client in `src/api/client.ts` follows [`../API_CONTRACT.md`](../API_CONTRACT.md). It expects `/users/me` to return a user object; ticket and user lists to return `{ items, page, limit, total }`; and created or updated records to return their record objects. IDs use `_id`. Password change sends `{ currentPassword, newPassword }`. If an API change is agreed, update the contract and the client together.

The frontend hides actions based on the signed-in user's role and ticket state. The backend remains the authority for ownership, permitted updates, and page limits.

Admins manage team names and responsibilities at `/teams`. Each team has an
**Add members** action with a paginated list of active people who have no team;
selections are retained across pages. Admins can also choose each user's team at
`/users` (`No team` removes membership), and filter the member list by a team or
**No team**, combined with role and account status. Ticket details show the saved
coordination summary, named teams, stakeholders, and analysis time. Team reasons
are kept in debug reports rather than shown in the interface.
The page checks for a fresh analysis every five seconds, up to twelve times when
the result is missing or older than the ticket. **Refresh** fetches the latest
saved result; it does not trigger a new agent run. Checks leave unsaved ticket
form fields intact. Express supplies display names, so viewing coordination
does not require access to admin directory endpoints.

The sample workspace includes teams and one saved example analysis on the Wi-Fi
ticket. It does not call the Python agent; new sample tickets have no analysis.

## Notifications

The header bell shows an unread badge and the five most recent notifications.
Opening an alert marks it as read and opens its ticket. The panel has individual
read controls, **Mark all as read**, and **View all**, with a full-width sheet on
mobile. Its native dialog supports Escape, focus trapping, and focus restoration.
The **Notifications** navigation item opens `/notifications`, with **All/Unread**
filters, pagination, and entries grouped into Today, Yesterday, and Earlier.
Unread entries use the existing pale yellow and blue palette. Empty/error/retry
states are displayed; deleted or inaccessible tickets keep readable notification
history with inactive ticket links.

Recent notifications and unread counts refresh every 30 seconds while the page
is visible, on window focus, and when opening the bell. The inbox and ticket
board refresh with those updates. The ticket board's **Involving me** filter
shows tickets where the current saved coordination lists the signed-in user as
a stakeholder, and combines with the existing filters and overview counts.
Employees can read affected tickets without gaining edit/delete permissions.
All requests use the existing session cookie and Express API; polling invokes no
agent calls. See the shared contract for notification response fields and events.

The existing development sample mode keeps a local notification history, starting
empty, and records sample ticket resolutions. Live notification verification uses
the configured API, database, and agent.

## Checks

```sh
npm run build
npm run test:e2e
```

The browser checks run against the sample workspace using installed Google Chrome. They cover employee, support, and admin flows, plus mobile navigation and viewport fit. They save inspection screenshots in the ignored `artifacts/` folder. The backend has separate API tests; a backend-connected browser check is still useful before deployment.

For deployment, configure the web server to serve `index.html` for client-side routes such as `/tickets/:id`.
