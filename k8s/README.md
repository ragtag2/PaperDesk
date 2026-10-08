# First k3s deployment on the Raspberry Pi

This local-network setup uses the already imported ARM64 images, `paperdesk-backend:pi` and `paperdesk-frontend:pi`. It serves the API at `http://172.20.10.2:30080` and the frontend at `http://172.20.10.2:30081`. If the Pi address changes, update `FRONTEND_ORIGIN` in `paperdesk.yaml` and rebuild the frontend image with the new `VITE_API_BASE_URL`.

## 1. Create the backend Secret on the Pi

```sh
sudo k3s kubectl create namespace paperdesk
openssl rand -hex 32
umask 077
nano ~/paperdesk-secret.env
```

Put these lines in `paperdesk-secret.env`, using your Atlas connection string and the random value printed by `openssl`. Include `MONGODB_DNS_SERVERS` when your connection needs the DNS setting from `backend/.env`:

```env
MONGODB_URI=mongodb+srv://USER:PASSWORD@CLUSTER/paperdesk
SESSION_SECRET=PASTE_RANDOM_VALUE_HERE
# Optional, when needed for Atlas SRV lookups:
MONGODB_DNS_SERVERS=1.1.1.1,8.8.8.8
```

Create the Kubernetes Secret without putting the credentials in the manifest:

```sh
sudo k3s kubectl -n paperdesk create secret generic paperdesk-backend --from-env-file="$HOME/paperdesk-secret.env"
```

If `backend/.env` already contains the correct `MONGODB_URI`, `SESSION_SECRET`, and `MONGODB_DNS_SERVERS`, you can copy that file to the Pi and use it as the `--from-env-file` source. The Docker image excludes `.env`; changing the local file does not update the Kubernetes Secret. To replace an existing Secret, use `create secret --dry-run=client -o yaml | kubectl apply -f -`, then restart the backend Deployment so it reads the new environment values.

The Pi must be able to connect to Atlas, including its Atlas IP access list entry.

## 2. Copy and apply the manifest

From PowerShell in the project root, with `$piIp = '172.20.10.2'`:

```powershell
scp .\k8s\paperdesk.yaml "rayen@${piIp}:~/paperdesk.yaml"
```

On the Pi:

```sh
sudo k3s kubectl apply -f ~/paperdesk.yaml
sudo k3s kubectl -n paperdesk rollout status deployment/paperdesk-backend --timeout=180s
sudo k3s kubectl -n paperdesk rollout status deployment/paperdesk-frontend --timeout=180s
sudo k3s kubectl -n paperdesk get pods,services
```

Open `http://172.20.10.2:30081` in a browser on the same network. An unsigned request to `http://172.20.10.2:30080/users/me` should return `401`, confirming that the API is reachable. If the backend does not become ready, inspect its logs:

```sh
sudo k3s kubectl -n paperdesk logs deployment/paperdesk-backend --tail=50
```

If the backend restarts and `kubectl logs` cannot retrieve its previous logs, first run `sudo k3s kubectl -n paperdesk describe secret paperdesk-backend` to confirm the expected key names are present. For a startup error that remains inaccessible, copy `backend-diagnostic.yaml` to the Pi, apply it, wait about 40 seconds, then run `sudo k3s kubectl -n paperdesk exec backend-diagnostic -- cat /tmp/backend-startup.log`. Remove the temporary pod with `sudo k3s kubectl -n paperdesk delete pod backend-diagnostic` afterward.

## Deploy the evaluated agent prompt

The current GitHub workflow tests pull requests into `main`. After a merge to
`main`, it builds ARM64 frontend, backend and agent images, publishes them to
GHCR, applies `paperdesk.yaml` and `agent.yaml` with the new image tags, and waits
for all three Deployments. A push to `feat/agent-evaluation` does not deploy to
production. Prepare the prompt label and production environment before merging.

### Production environment on the Pi

The agent container reads `paperdesk-agent` through `envFrom`. Its MongoDB URI
and optional DNS settings come from `paperdesk-backend`, and the agent manifest
explicitly selects the application database `paperdesk`. Local Windows `.env`
changes do not update the Pi's Secret.

In Langfuse, assign `production` to the approved version of the **text** prompt
`ticket-analysis-system`. The project keys in the agent environment must belong
to the project holding this prompt.

On the Pi, edit the env file used to manage the existing `paperdesk-agent`
Secret (the commands below use `~/paperdesk-agent.env`). Preserve its other
settings and add or update:

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-your-project-key
LANGFUSE_SECRET_KEY=sk-lf-your-project-secret
LANGFUSE_BASE_URL=http://LANGFUSE_HOST_REACHABLE_FROM_PI:3001
LANGFUSE_TRACING_ENVIRONMENT=production
LANGFUSE_TRACING_ENABLED=true

AGENT_MODEL=openai:lightning-ai/deepseek-v4.1-flash
AGENT_MODEL_BASE_URL=https://lightning.ai/api/v1/
AGENT_MODEL_API_KEY=your-existing-lightning-api-key
AGENT_MODEL_TIMEOUT_SECONDS=20
AGENT_MODEL_MAX_TOKENS=2048
```

Replace the URL with the actual reachable Langfuse endpoint. For Langfuse hosted
on the Windows machine, use that machine's LAN address when both devices share
the network; `localhost` inside the Pi's agent container refers to the container
itself. The Windows host and Langfuse service must be reachable from the Pi.
Use the same model settings as the successful evaluations.

```sh
umask 077
nano ~/paperdesk-agent.env
sudo k3s kubectl -n paperdesk create secret generic paperdesk-agent --from-env-file="$HOME/paperdesk-agent.env" --dry-run=client -o yaml | sudo k3s kubectl apply -f -
```

### Commit the branch and deploy through main

From Windows, review the branch changes, including the existing prompt override
and Lightning adapter. Stage the tracked agent/experiment changes and explicitly
add the new runner and test files. Then commit and push the feature branch:

```powershell
git status --short
git add -u -- agents experiments k8s/README.md
git add -- agents/tests/test_experiments.py agents/tests/test_model.py experiments/run.py experiments/evaluators.py experiments/check_model.py
git diff --cached --stat
git commit -m "Use evaluated Langfuse production prompt at agent startup"
git push -u origin feat/agent-evaluation
```

These paths include the earlier experiment/model changes needed by the startup
integration. Root `API_CONTRACT.md` and `WORK_LOG.md` remain local, ignored project
records. The staging commands leave local credentials, analysis reports,
`light.py`, and the experiment bytecode directory out of the commit.

Open a pull request from `feat/agent-evaluation` into `main`. Run or let CI run
the offline agent checks before merging:

```powershell
.\agents\.venv\Scripts\python.exe -m unittest discover -s agents/tests -v
```

After the prompt/environment are ready and CI passes, merge the pull request.
Watch the GitHub Actions image and Pi deployment jobs. The new image rollout
starts a new agent process that fetches the production prompt at startup.

### Verify and restart after later prompt changes

On the Pi:

```sh
sudo k3s kubectl -n paperdesk rollout status deployment/paperdesk-agent --timeout=240s
sudo k3s kubectl -n paperdesk logs deployment/paperdesk-agent --tail=50
```

The ready log should show `ticket-analysis-system@3` when version 3 holds
`production`. Create or update an ordinary application ticket, then inspect its
Langfuse trace or local report for the same `promptVersion` value. The backend
manifest already uses `AGENT_BASE_URL=http://paperdesk-agent:8000`.

For a later Secret update, prompt promotion, or rollback, restart the agent so
it loads the new environment and resolves the label again:

```sh
sudo k3s kubectl -n paperdesk rollout restart deployment/paperdesk-agent
sudo k3s kubectl -n paperdesk rollout status deployment/paperdesk-agent --timeout=240s
sudo k3s kubectl -n paperdesk logs deployment/paperdesk-agent --tail=50
```

Restarting the existing image reloads its configuration; deploying the code
change requires the merged branch's new image. The service fetches once per
process startup and has no built-in prompt fallback when Langfuse is unavailable.
Post-startup telemetry failures still leave ticket analyses working.
