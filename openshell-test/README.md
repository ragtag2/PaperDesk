# Paperdesk terminal test on OpenShell 0.1.3

Prepared 2026-10-10 for Ubuntu 22.04 in VMware, an authenticated local OpenShell
0.1.3 gateway, and its Docker compute driver. No GPU is needed: model inference
runs at Lightning. The existing Dockerfile, Kubernetes manifests, application
code, and `.env` files are preserved. These are standalone test instructions and
two configuration files; no application code change is required.

For a separate synthetic prompt injection experiment, see
[the terminal injection demo](injection-demo.md). It adds a temporary HTTP tool
only for that process and documents how to verify an actual OpenShell denial.

The installed CLI/gateway version and Docker driver were confirmed from your
terminal output. This Windows workspace cannot execute the VM's installed CLI.
Command options below were checked against NVIDIA's **v0.1.3** documentation and
CLI argument definitions. The first step includes local help checks. This setup
has not been launched on your VM.

## What the project needs

| Item | Findings from the project |
| --- | --- |
| Python | `agents/Dockerfile` uses Python 3.12 on Debian Bookworm; the VM host remains Ubuntu 22.04. |
| Dependencies | `fastapi>=0.115,<1`, `uvicorn>=0.30,<1`, `langchain>=1.0,<2`, `langchain-openai>=1.0,<2`, `langchain-groq>=1.1.3,<2`, `langfuse>=4.17,<5`, `pymongo>=4.10,<5`, `dnspython>=2.6,<3`, `python-dotenv>=1.0,<2`. These are ranges, not a dependency lockfile. |
| Model | The inspected local configuration selects `openai:lightning-ai/deepseek-v4.1-flash` at `https://lightning.ai/api/v1/`, authenticated by `AGENT_MODEL_API_KEY`. This uses the existing Lightning/DeepSeek compatibility adapter in `agents/model.py`. A configured Groq key does not select Groq. |
| MongoDB | The local configuration uses authenticated Atlas through `mongodb+srv://`; database `paperdesk`. The agent reads `tickets`, `teams`, and active users with `teamId` from `users`. It performs no database writes. Use an Atlas database user with `read` on `paperdesk`, and allow the VM's public egress IP in Atlas Network Access. VMware NAT uses the upstream network's public egress IP. |
| Reports | `agents/reporting.py` fixes the location relative to its source: `/app/agents/runs/analyses/<ticketId>/<analysisId>.json` in this image. There is no report-directory environment setting. Reports include status, result, checks, timing, and model/tool/token metrics, including analysis failures. |
| Prompt and tracing | `agents/main.py` requires Langfuse keys and the production label of text prompt `ticket-analysis-system`. The configured Langfuse address is `http://localhost:3001`, which is not a Windows-host address from this VM. The terminal test below uses `IncidentCoordinator` directly with its built-in prompt and tracing disabled. It therefore exercises real MongoDB/model calls without requiring Langfuse or starting FastAPI, Express, or React. It does not verify the production Langfuse prompt. |

`Settings.from_env()` also loads an adjacent `agents/.env` when present. The
existing Docker build excludes `.env*`, and these commands never upload an env
file. Configuration for this test is explicit:

| Variable | Test setting |
| --- | --- |
| `MONGODB_URI` | Private URI passed to one Python process over stdin; never stored in sandbox create/exec arguments or an env file. |
| `MONGODB_DB_NAME` | `paperdesk` |
| `AGENT_MODEL` | `openai:lightning-ai/deepseek-v4.1-flash` |
| `AGENT_MODEL_BASE_URL` | `https://lightning.ai/api/v1/` |
| `AGENT_MODEL_API_KEY` | An OpenShell provider placeholder inside the sandbox; actual key stays in the gateway credential store. |
| `AGENT_MODEL_TIMEOUT_SECONDS` | `20` per model call |
| `AGENT_MODEL_MAX_TOKENS` | `2048` per model call |
| `LANGFUSE_TRACING_ENABLED` | `false` |
| `MONGODB_DNS_SERVERS` | Optional **host helper** setting for Atlas SRV expansion; not needed inside the sandbox after expansion. |

The other supported settings are `GROQ_API_KEY`, `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, and
`LANGFUSE_TRACING_ENVIRONMENT`. They are not supplied for this direct test.

## 1. Start in the project copy on the Ubuntu VM

Copy/check out the project and this `openshell-test/` directory on the VM first.
Run the following in **Bash** from the project root. There is no assumed VM
checkout path.

```bash
cd /absolute/path/to/ticketSubmission
set +x
set -e -o pipefail
umask 077
export PAPERDESK_PROJECT_ROOT="$PWD"
export PAPERDESK_IMAGE=paperdesk-openshell:0.1.3
export PAPERDESK_SANDBOX=paperdesk-013
export PAPERDESK_WORKSPACE=default
export PAPERDESK_REPORT_VOLUME=paperdesk-reports-013
export PAPERDESK_STATE_DIR="$HOME/.local/share/paperdesk-openshell-013"
mkdir -p "$PAPERDESK_STATE_DIR"

openshell --version
openshell status
openshell gateway info
openshell sandbox create --help
openshell sandbox exec --help
openshell provider create --help
openshell profile import --help
docker info >/dev/null
uname -r
```

Keep using the connected `local` gateway. If using a workspace other than
`default`, set `PAPERDESK_WORKSPACE` to that workspace before the following steps.
Use unused sandbox/provider/profile names on the first run.

## 2. Build the image without changing the existing Dockerfile

The first build uses the existing `agents/.dockerignore` and Dockerfile. It
excludes env files, virtual environments, reports, and tests. Its `COPY *.py`
includes the modules required by the direct coordinator call.

The second build only makes `/app` writable by the existing non-root image user:
OpenShell 0.1.3 checks ownership of the image's working directory before launch.
The filesystem policy subsequently permits application writes only under the
report directory and temporary paths.

```bash
docker build --tag paperdesk-openshell-base:0.1.3 \
  "$PAPERDESK_PROJECT_ROOT/agents"

docker build --tag "$PAPERDESK_IMAGE" - <<'DOCKERFILE'
FROM paperdesk-openshell-base:0.1.3
USER root
RUN chown paperdesk:paperdesk /app
USER paperdesk
DOCKERFILE

docker run --rm --network none --entrypoint /bin/sh "$PAPERDESK_IMAGE" -c \
  'id; readlink -f /usr/local/bin/python; test -w /app; test ! -e /app/agents/.env'
```

Expected identity: UID/GID `10001`; interpreter
`/usr/local/bin/python3.12`. The policy/profile name that actual executable.
Dependencies install during the Docker build, so the running sandbox needs no
PyPI or OS package-registry access. In 0.1.3, `--from` takes the built image tag;
it does not build a local Dockerfile.

## 3. Enable persistent, approved Docker volume attachments

OpenShell 0.1.3 disables caller driver JSON by default. Named volume attachments
also require approval labels. This is a gateway configuration change, not an
application change. Preserve all existing TLS, authentication, and driver
settings.

For the standard Debian/Ubuntu systemd user installation, the configuration is
`${XDG_CONFIG_HOME:-$HOME/.config}/openshell/gateway.toml`. A configured
`--config` or `OPENSHELL_GATEWAY_CONFIG` takes precedence: edit that active file
instead when applicable. Check the service launch arguments with
`systemctl --user show openshell-gateway -p ExecStart` if necessary; do not dump
the service environment.

```bash
PAPERDESK_GATEWAY_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/openshell/gateway.toml"
mkdir -p "$(dirname "$PAPERDESK_GATEWAY_CONFIG")"
if [ -f "$PAPERDESK_GATEWAY_CONFIG" ]; then
  cp -p -- "$PAPERDESK_GATEWAY_CONFIG" \
    "$PAPERDESK_GATEWAY_CONFIG.before-paperdesk-$(date -u +%Y%m%dT%H%M%SZ)"
else
  printf '[openshell]\nversion = 2\n' > "$PAPERDESK_GATEWAY_CONFIG"
fi
nano "$PAPERDESK_GATEWAY_CONFIG"
```

Merge the following into the existing tables; **do not duplicate table headers**:

```toml
[openshell.drivers.docker]
allow_driver_config = true

[openshell.drivers.docker.resource_admission]
enabled = true

[openshell.drivers.docker.resource_admission.required_labels]
"openshell.ai/sandbox-attachable" = "true"
"openshell.ai/sandbox-attachable-workspace" = "${workspace}"
```

The literal `${workspace}` is OpenShell's substitution, not a shell variable.
Those labels are the official defaults. If you already have a custom required
label map, retain it and label the volume to satisfy that map instead.
No bind-mount opt-in is required.

```bash
openshell-gateway config preflight --path "$PAPERDESK_GATEWAY_CONFIG"
systemctl --user restart openshell-gateway
openshell status

docker volume create \
  --label openshell.ai/sandbox-attachable=true \
  --label "openshell.ai/sandbox-attachable-workspace=$PAPERDESK_WORKSPACE" \
  "$PAPERDESK_REPORT_VOLUME"

docker run --rm --network none --user 0:0 \
  --mount "type=volume,source=$PAPERDESK_REPORT_VOLUME,target=/app/agents/runs" \
  --entrypoint /bin/sh "$PAPERDESK_IMAGE" -c \
  'mkdir -p /app/agents/runs/analyses && chown -R 10001:10001 /app/agents/runs && chmod 700 /app/agents/runs'
```

If the gateway was launched manually or via Snap, restart that existing gateway
process/service with its existing launch configuration instead of using the
systemd command. The volume is external to the sandbox and survives sandbox
deletion. Its mount target is below `/app`, so it does not cover OpenShell's
workspace root. The user-supplied volume is never removed by the Docker driver.

## 4. Register Lightning credentials without writing a secret file

The adjacent `lightning-profile.yaml` binds `AGENT_MODEL_API_KEY` to Lightning's
Chat Completions endpoint for Python 3.12. This preserves Paperdesk's existing
model adapter. An OpenAI profile bound to `api.openai.com` would not authorize
the same credential at `lightning.ai`.

```bash
openshell profile lint --workspace "$PAPERDESK_WORKSPACE" \
  -f "$PAPERDESK_PROJECT_ROOT/openshell-test/lightning-profile.yaml"
openshell profile import --workspace "$PAPERDESK_WORKSPACE" \
  -f "$PAPERDESK_PROJECT_ROOT/openshell-test/lightning-profile.yaml"

read -r -s -p 'Lightning API key: ' AGENT_MODEL_API_KEY
printf '\n'
export AGENT_MODEL_API_KEY
openshell provider create --workspace "$PAPERDESK_WORKSPACE" \
  --name paperdesk-lightning-013 --type paperdesk-lightning-013 --from-existing
unset AGENT_MODEL_API_KEY
```

Import and create are first-run operations. On a repeat run, keep the existing
profile/provider. To rotate the key, use the same private prompt/export and
`openshell provider update --workspace "$PAPERDESK_WORKSPACE" paperdesk-lightning-013 --from-existing --wait`,
then unset the key and launch a fresh test process.

## 5. Prepare the Atlas URI in memory and render the policy YAML

OpenShell 0.1.3's policy DNS implements A/AAAA, not SRV/TXT queries. Its native
TCP tunnel also cannot replace MongoDB authentication credentials. Consequently:

1. Resolve the Atlas SRV/TXT information on the VM before sandbox execution.
2. Use the resulting standard `mongodb://` URI, with TLS still enabled.
3. Pass that URI over stdin into the single test process.

The helper container below uses the already-built image and host networking
only for DNS resolution, outside OpenShell. It makes no database connection.
Docker logging is disabled for this helper, and its stdout is captured into a
shell variable, never displayed. Only member
hostnames and ports go into the policy file. The original URI's encoded
username/password, database path, and query options are preserved; TXT-derived
authentication/replica-set settings and the SRV TLS default are carried over.

```bash
read -r -s -p 'Atlas MongoDB URI: ' PAPERDESK_MONGODB_URI
printf '\n'

# Optional if your VM resolver needs the same workaround as agents/.env:
# export MONGODB_DNS_SERVERS=1.1.1.1,8.8.8.8

PAPERDESK_MONGODB_URI="$(
  printf '%s' "$PAPERDESK_MONGODB_URI" |
  docker run --rm -i --log-driver none --network host --env MONGODB_DNS_SERVERS \
    --entrypoint /usr/local/bin/python3.12 "$PAPERDESK_IMAGE" -c '
import os, sys
from urllib.parse import parse_qsl, urlencode, urlsplit
import dns.resolver
from pymongo.uri_parser import parse_uri
try:
    uri = sys.stdin.read().strip()
    servers = [s.strip() for s in os.getenv("MONGODB_DNS_SERVERS", "").split(",") if s.strip()]
    if servers:
        dns.resolver.get_default_resolver().nameservers = servers
    parsed = parse_uri(uri)
    options = {key.lower(): value for key, value in parsed["options"].items()}
    if not options.get("tls", False):
        raise ValueError("Atlas TLS is required")
    if uri.startswith("mongodb+srv://"):
        source = urlsplit(uri)
        query = parse_qsl(source.query, keep_blank_values=True)
        keys = {key.lower() for key, _ in query}
        if keys & {"srvservicename", "srvmaxhosts"}:
            raise ValueError("Nondefault SRV selection needs a separately prepared standard URI")
        for key in ("authsource", "replicaset", "loadbalanced", "tls"):
            value = options.get(key)
            if value is not None and key not in keys and not (key == "tls" and "ssl" in keys):
                query.append((key, str(value).lower() if isinstance(value, bool) else str(value)))
        credentials = source.netloc.rsplit("@", 1)[0] + "@" if "@" in source.netloc else ""
        seeds = ",".join(f"{host}:{port}" for host, port in parsed["nodelist"])
        uri = "mongodb://" + credentials + seeds + source.path + "?" + urlencode(query)
    if not uri.startswith("mongodb://"):
        raise ValueError("A standard MongoDB URI is required")
    print(uri, end="")
except Exception as error:
    print("Atlas URI preparation failed: " + type(error).__name__, file=sys.stderr)
    sys.exit(1)
'
)"
test -n "$PAPERDESK_MONGODB_URI"
```

If preparation fails, stop this step and correct the VM DNS/URI before proceeding.
Do not print the variable to diagnose it. A standard Atlas URI must include its
TLS option and any required replica-set/authentication options. A topology change
requires preparing the URI and regenerating the member policy again.

Render the adjacent template into the required policy YAML:

```bash
printf '%s' "$PAPERDESK_MONGODB_URI" |
docker run --rm -i --network none --user 0:0 \
  --mount "type=bind,source=$PAPERDESK_PROJECT_ROOT/openshell-test/policy.template.yaml,target=/policy.template.yaml,readonly" \
  --entrypoint /usr/local/bin/python3.12 "$PAPERDESK_IMAGE" -c '
import json, sys
from pathlib import Path
from pymongo.uri_parser import parse_uri
try:
    uri = sys.stdin.read().strip()
    if not uri.startswith("mongodb://"):
        raise ValueError("Expand SRV outside the sandbox first")
    nodes = sorted(set(parse_uri(uri)["nodelist"]))
    if not nodes or any(not host.endswith(".mongodb.net") for host, _ in nodes):
        raise ValueError("This policy recipe is for public Atlas member hosts")
    endpoints = "    endpoints:\n" + "".join(
        "      - host: " + json.dumps(host) + "\n"
        + "        port: " + str(port) + "\n"
        + "        protocol: tcp\n"
        + "        tls: skip\n"
        for host, port in nodes
    )
    template = Path("/policy.template.yaml").read_text()
    marker = "    endpoints: [] # REPLACED_FROM_MONGODB_URI\n"
    if template.count(marker) != 1:
        raise ValueError("Invalid policy template")
    sys.stdout.write(template.replace(marker, endpoints))
except Exception as error:
    print("Policy rendering failed: " + type(error).__name__, file=sys.stderr)
    sys.exit(1)
' > "$PAPERDESK_STATE_DIR/policy.yaml"
test -s "$PAPERDESK_STATE_DIR/policy.yaml"
```

The resulting policy has one exact `host`/`port` entry per Atlas seed, each with
`protocol: tcp` and `tls: skip`. MongoDB performs and verifies TLS end to end;
`tls: skip` disables OpenShell's TLS interception, not MongoDB encryption. TCP
endpoints must not have REST access/enforcement/request-rule fields. Database
read permission comes from the Atlas user, because OpenShell does not inspect
MongoDB wire operations. The Lightning provider contributes the separate,
inspected HTTPS rule. No broad internet or public DNS endpoint rule is needed.

## 6. Launch the sandbox

```bash
openshell sandbox create --workspace "$PAPERDESK_WORKSPACE" \
  --name "$PAPERDESK_SANDBOX" \
  --from "$PAPERDESK_IMAGE" \
  --policy "$PAPERDESK_STATE_DIR/policy.yaml" \
  --provider paperdesk-lightning-013 \
  --no-auto-providers \
  --cpu 2 --memory 2Gi \
  --driver-config-json "{\"docker\":{\"mounts\":[{\"type\":\"volume\",\"source\":\"$PAPERDESK_REPORT_VOLUME\",\"target\":\"/app/agents/runs\",\"read_only\":false}]}}" \
  --env MONGODB_DB_NAME=paperdesk \
  --env AGENT_MODEL=openai:lightning-ai/deepseek-v4.1-flash \
  --env AGENT_MODEL_BASE_URL=https://lightning.ai/api/v1/ \
  --env AGENT_MODEL_TIMEOUT_SECONDS=20 \
  --env AGENT_MODEL_MAX_TOKENS=2048 \
  --env LANGFUSE_TRACING_ENABLED=false \
  --detach -- /bin/sleep infinity

openshell policy get --workspace "$PAPERDESK_WORKSPACE" "$PAPERDESK_SANDBOX" --full
```

The canonical process keeps the sandbox available for terminal commands. No
service port is exposed. Mounts are read-only by default in 0.1.3, so
`read_only:false` is required for reports. A fresh sandbox uses the current
filesystem and process policy; those sections cannot be changed live.

## 7. Run one real ticket analysis from the terminal

The command defaults to the newest existing ticket. To select one, first run
`export PAPERDESK_TICKET_ID=YOUR_EXISTING_24_HEX_OBJECT_ID`; that ID is not a secret.
Teams and memberships must already exist if you expect nonempty routing results.
This test does not seed or update the database.

```bash
printf '%s' "$PAPERDESK_MONGODB_URI" |
openshell sandbox exec --workspace "$PAPERDESK_WORKSPACE" \
  --name "$PAPERDESK_SANDBOX" --no-tty --no-login-shell \
  --workdir /app --timeout 600 \
  --env "PAPERDESK_TICKET_ID=${PAPERDESK_TICKET_ID:-}" \
  -- /usr/local/bin/python3.12 -c '
import json, logging, os, sys
logging.disable(logging.CRITICAL)
client = None
stage = "configuration"
try:
    os.environ["MONGODB_URI"] = sys.stdin.read().strip()
    from agents.agent import IncidentCoordinator
    from agents.config import Settings
    from agents.database import MongoDatabase, create_mongo_client
    from agents.model import create_model
    from agents.reporting import ANALYSES_DIRECTORY
    from agents.schemas import AnalyzeTicketRequest
    settings = Settings.from_env()
    if not settings.model_api_key.startswith("openshell:"):
        raise RuntimeError("Expected an OpenShell provider credential reference")
    stage = "mongodb"
    client = create_mongo_client(settings)
    client.admin.command("ping")
    database = MongoDatabase(client[settings.mongodb_db_name])
    ticket_id = os.environ.get("PAPERDESK_TICKET_ID", "")
    if not ticket_id:
        ticket = database.database.tickets.find_one(
            {}, {"_id": 1}, sort=[("createdAt", -1), ("_id", -1)]
        )
        if ticket is None:
            raise RuntimeError("No existing ticket")
        ticket_id = str(ticket["_id"])
    ticket_id = AnalyzeTicketRequest(ticketId=ticket_id).ticketId.lower()
    report_dir = ANALYSES_DIRECTORY / ticket_id
    previous_reports = set(report_dir.glob("*.json"))
    stage = "model-and-analysis"
    coordinator = IncidentCoordinator(database, create_model(settings), model_name=settings.model)
    result = coordinator.analyze(ticket_id)
    stage = "validation-and-report-storage"
    known_teams = {team["_id"] for team in database.list_teams()}
    selected = [team.teamId for team in result.relevantTeams]
    expected = {
        member["_id"] for team_id in selected
        for member in database.get_team_members(team_id)
    }
    checks = {
        "ticketIdMatches": result.ticketId == ticket_id,
        "teamsExist": set(selected) <= known_teams,
        "uniqueTeams": len(selected) == len(set(selected)),
        "stakeholdersMatchActiveMembers": set(result.stakeholderUserIds) == expected,
        "uniqueStakeholders": len(result.stakeholderUserIds) == len(set(result.stakeholderUserIds)),
    }
    reports = set(report_dir.glob("*.json")) - previous_reports
    checks["reportPersisted"] = len(reports) == 1
    if not all(checks.values()):
        raise RuntimeError("Result validation or report persistence failed")
    report_path = reports.pop()
    report = json.loads(report_path.read_text())
    if report["status"] != "passed" or report["result"] != result.model_dump(mode="json"):
        raise RuntimeError("Saved report does not match the result")
    print(json.dumps({"status": "passed", "result": result.model_dump(mode="json"),
                      "checks": checks, "report": str(report_path)}, indent=2))
except Exception as error:
    print(json.dumps({"status": "failed", "stage": stage,
                      "errorType": type(error).__name__}), file=sys.stderr)
    sys.exit(1)
finally:
    if client is not None:
        client.close()
'
```

Success prints `"status": "passed"`, the coordination result, all validation
checks as `true`, and the saved JSON path. The CLI propagates the process exit
status. Errors print only stage and exception type, without URI/key values or
raw tracebacks. Analysis reports use the existing agent credential redaction.
Reports contain ticket-derived business data, so the dedicated volume is private
to UID 10001.

## 8. Export reports and end the test

The named volume already provides persistence. To also save a timestamped archive
on the VM filesystem:

```bash
docker run --rm --network none --user 10001:10001 \
  --mount "type=volume,source=$PAPERDESK_REPORT_VOLUME,target=/reports,readonly" \
  --entrypoint /bin/tar "$PAPERDESK_IMAGE" -C /reports -cf - . \
  > "$PAPERDESK_STATE_DIR/reports-$(date -u +%Y%m%dT%H%M%SZ).tar"

unset PAPERDESK_MONGODB_URI
openshell sandbox stop --workspace "$PAPERDESK_WORKSPACE" "$PAPERDESK_SANDBOX"
```

The archive is created with the shell's private umask. To run again in a new
shell, restore the non-secret variables from step 1 and privately prepare the
MongoDB URI again. Reuse the existing provider and report volume; create a new
sandbox name or restart the retained sandbox using the installed CLI's lifecycle
commands. No credentials are persisted by this runbook in an env file, policy,
profile, Docker build argument, or application image.

## Troubleshooting specific to this setup

| Failure | Action |
| --- | --- |
| Name exceeds maximum length | This gateway reported a 19-character sandbox-name limit. Use `export PAPERDESK_SANDBOX=paperdesk-013` and retry creation; no image rebuild is needed. |
| Driver config disabled / unapproved volume | Verify the active gateway config has `allow_driver_config=true`, restart it, and verify the engine volume has the required workspace approval labels. Changing sandbox labels does not approve a volume. |
| Workdir or identity rejected | Confirm the wrapper image was built, `/app` is owned by `paperdesk`, and image/policy UID/GID are 10001. |
| Landlock/seccomp startup failure | 0.1.3 requires Landlock ABI v3 or newer and working seccomp user notification. Ubuntu 22.04's original 5.15 kernel is too old for Landlock ABI v3; a supported HWE kernel may be needed. Check the actual VM kernel and the startup error. This policy requests filesystem enforcement explicitly. |
| MongoDB stage fails | Check Atlas database-user access, the VM's public egress IP entry, TLS and replica-set options, and the current member hostnames. Do not pass `mongodb+srv://` inside this sandbox. |
| HTTP 403 / model stage fails | Confirm the attached custom provider exposes `AGENT_MODEL_API_KEY`, Python resolves to `/usr/local/bin/python3.12`, and the effective policy includes the Lightning provider rule. |
| No analysis report | The test checks persistence explicitly because the application's report writer logs filesystem errors without failing a valid result. Verify the volume's ownership and `read_only:false`. |
| `agents.scripts.run_live` unavailable / Langfuse startup fails | The existing image copies top-level agent modules, not scripts. This runbook uses the direct coordinator command above. The separate HTTP runner needs the script packaged plus reachable Langfuse and its production prompt. |

## Official references pinned to v0.1.3

- [CLI argument definitions](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/crates/openshell-cli/src/main.rs)
- [Sandbox lifecycle, image sources, exec and stdin](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/docs/how-it-works/sandboxes/overview.mdx)
- [Docker driver: identity, persistence and mounts](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/crates/openshell-driver-docker/README.md)
- [Gateway configuration and external resource admission](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/docs/how-it-works/gateways/configuration.mdx#external-resource-admission)
- [Policy schema](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/docs/how-it-works/policies/schema.mdx)
- [Native TCP and TLS handling](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/docs/how-it-works/policies/network-rules.mdx#allow-native-tcp)
- [Provider commands and private credential discovery](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/docs/how-it-works/providers/overview.mdx)
- [Profile schema and static credential endpoint binding](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/docs/how-it-works/providers/profiles.mdx)
- [Official OpenAI profile used as the custom-profile reference](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/providers/openai.yaml)
- [DNS wire implementation: A/AAAA only](https://github.com/NVIDIA/OpenShell/blob/v0.1.3/crates/openshell-supervisor-network/src/policy_dns/wire.rs)
