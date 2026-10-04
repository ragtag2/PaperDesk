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
