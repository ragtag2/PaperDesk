# Ticket submission project

Product requirements are in [`mvp.docx`](mvp.docx). The [API contract](API_CONTRACT.md) defines the frontend/backend agreement. The React app lives in [`frontend/`](frontend/) and the Express API in [`backend/`](backend/). Each folder has its own README and package commands.

```sh
cd frontend
npm install
npm run dev
```

In this Windows PowerShell environment, use `npm.cmd` instead of `npm` if script execution is disabled.

The root `AGENTS.md` contains shared guidance; `frontend/AGENTS.md` and `backend/AGENTS.md` contain area-specific guidance. `WORK_LOG.md` records coding requests and completed code changes.

## Package images for the Raspberry Pi

The two Dockerfiles build Linux ARM64 images. The frontend image serves the Vite build through Nginx, including direct visits to React routes. The backend image runs the compiled Express app. Build on the Windows PC with Docker Desktop running. In the commands below, replace `<PI_IP>` with the Pi's LAN address (`hostname -I` on the Pi). Port `30080` is the planned API NodePort for the next deployment step.

```powershell
$piIp = '172.20.10.2'
docker buildx build --platform linux/arm64 --load -t paperdesk-backend:pi ./backend
docker buildx build --platform linux/arm64 --load --build-arg "VITE_API_BASE_URL=http://${piIp}:30080" -t paperdesk-frontend:pi ./frontend
docker save --platform linux/arm64 -o paperdesk-images.tar paperdesk-backend:pi paperdesk-frontend:pi
scp .\paperdesk-images.tar "rayen@${piIp}:~/"
```

The frontend API URL is embedded in its JavaScript at build time. Rebuild that image if the API address changes. The Docker build excludes local environment files. On the Pi, import the images into k3s:

```sh
sudo k3s ctr -n k8s.io images import ~/paperdesk-images.tar
sudo k3s ctr -n k8s.io images list | grep paperdesk
```

The Kubernetes Deployments and Services are in `k8s/paperdesk.yaml`. The backend needs `MONGODB_URI`, `SESSION_SECRET`, and `FRONTEND_ORIGIN` at runtime; for the planned frontend NodePort, `FRONTEND_ORIGIN` is `http://<PI_IP>:30081`. Keep the same `SESSION_SECRET` across restarts.

The first local-network deployment is in [`k8s/`](k8s/README.md).
