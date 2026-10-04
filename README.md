# Paperdesk

Paperdesk is an AI-assisted ticket and incident management application for internal support. Employees submit tickets, support staff assign and resolve them, and admins manage users, roles, and teams.

AI incident coordination summarizes issues, identifies responsible or affected teams, and determines which people should be involved. The app also includes ticket filtering, profile settings, and notifications about ticket involvement and resolution.

## Architecture

```mermaid
flowchart LR
    Frontend["Frontend (React)"] <-->|REST API| Backend["Backend (Express)"]
    Backend <-->|Application data| Database[(MongoDB Atlas)]
    Backend -->|Background incident analysis| Agent["AI coordination service (Python)"]
    Agent -->|Read ticket and team data| Database
```

The frontend communicates with the backend using a session cookie. The backend handles permissions and database operations. For incident coordination, it calls the Python agent in the background and saves the returned summary, relevant teams, and stakeholders.

## Project parts

| Part | Technology | Responsibility |
| --- | --- | --- |
| [Frontend](frontend/README.md) | React, TypeScript, Vite | Browser interface for login, tickets, notifications, profiles, and administration. |
| [Backend](backend/README.md) | Express, TypeScript, Node.js | REST API, authentication, permissions, ticket management, and notifications. |
| [AI coordination service](agents/README.md) | Python, FastAPI, LangChain | Analyzes incident context, produces summaries, and identifies relevant teams and stakeholders. |
| [Deployment](k8s/README.md) | Docker images, Kubernetes manifests, k3s | Configuration for running and exposing the frontend and backend on the Raspberry Pi. |
| Database | MongoDB Atlas | Stores users, teams, tickets, sessions, and notifications. |

Each component's linked README contains its setup instructions.

## Current deployment

The frontend and backend run as ARM64 containers on a Raspberry Pi 4 through k3s. Nginx serves the frontend, and Node.js runs the backend. MongoDB Atlas is hosted separately. The Python coordination agent is a separate service and has not yet been deployed on the Pi.

The current manifests expose the frontend on port `30081` and the API on port `30080`. See the [deployment guide](k8s/README.md) for configuration and deployment steps.
