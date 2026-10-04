"""Start FastAPI, analyze a real MongoDB ticket, and save the HTTP result."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from datetime import datetime, timezone
from time import monotonic, perf_counter, sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from agents.config import Settings
from agents.database import MongoDatabase, create_mongo_client
from agents.reporting import safe_error
from agents.schemas import AnalyzeTicketRequest, CoordinationResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIRECTORY = PROJECT_ROOT / "agents" / "runs" / "analyses"


def wait_for_server(base_url: str, process: subprocess.Popen | None) -> None:
    deadline = monotonic() + 20
    while monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("Agent exited during startup. See the saved service log.")
        try:
            with urlopen(f"{base_url}/openapi.json", timeout=2) as response:
                document = json.load(response)
                if "/analyze-ticket" not in document.get("paths", {}):
                    raise RuntimeError("The selected port is not running the ticket agent.")
                return
        except (URLError, TimeoutError, ConnectionError):
            sleep(0.2)
    raise RuntimeError("Agent did not become ready within 20 seconds.")


def check_result(result: CoordinationResult, ticket_id: str, database: MongoDatabase) -> dict:
    teams = {team["_id"] for team in database.list_teams()}
    selected = [team.teamId for team in result.relevantTeams]
    expected_members = {
        member["_id"]
        for team_id in selected
        if team_id in teams
        for member in database.get_team_members(team_id)
    }
    return {
        "ticketIdMatches": result.ticketId == ticket_id,
        "teamsExist": all(team_id in teams for team_id in selected),
        "uniqueTeams": len(selected) == len(set(selected)),
        "stakeholdersMatchActiveMembers": set(result.stakeholderUserIds) == expected_members,
        "uniqueStakeholders": len(result.stakeholderUserIds) == len(set(result.stakeholderUserIds)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-id", help="Existing ticket ID; defaults to the latest ticket.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--use-running-agent", action="store_true", help="Use an existing service.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    RUNS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    report_path = RUNS_DIRECTORY / "live-checks" / f"{run_id}-live.json"
    log_path = RUNS_DIRECTORY / "live-checks" / f"{run_id}-service.log"
    report = {"startedAt": datetime.now(timezone.utc).isoformat(), "status": "failed"}
    process = None
    log_stream = None
    client = None
    started = perf_counter()
    try:
        settings = Settings.from_env()
        report["model"] = settings.model
        client = create_mongo_client(settings)
        client.admin.command("ping")
        database = MongoDatabase(client[settings.mongodb_db_name])
        ticket_id = args.ticket_id
        if ticket_id is None:
            ticket = database.database.tickets.find_one({}, {"_id": 1}, sort=[("createdAt", -1), ("_id", -1)])
            if ticket is None:
                raise RuntimeError("No tickets exist. Create a ticket in Paperdesk, then rerun this command.")
            ticket_id = str(ticket["_id"])
        ticket_id = AnalyzeTicketRequest(ticketId=ticket_id).ticketId.lower()
        report_path = RUNS_DIRECTORY / ticket_id / f"{run_id}-live.json"
        log_path = RUNS_DIRECTORY / ticket_id / f"{run_id}-service.log"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        ticket = database.get_ticket(ticket_id)
        report["ticketId"] = ticket_id
        report["ticketTitle"] = ticket["title"]
        report["teamCount"] = len(database.list_teams())

        base_url = f"http://127.0.0.1:{args.port}"
        if not args.use_running_agent:
            with socket.socket() as connection:
                if connection.connect_ex(("127.0.0.1", args.port)) == 0:
                    raise RuntimeError("Port is already in use. Choose --port or pass --use-running-agent.")
            log_stream = log_path.open("w", encoding="utf-8")
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "agents.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
                cwd=PROJECT_ROOT,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            report["serviceLog"] = str(log_path.relative_to(PROJECT_ROOT))
        wait_for_server(base_url, process)
        request = Request(
            f"{base_url}/analyze-ticket",
            data=json.dumps({"ticketId": ticket_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        request_started = perf_counter()
        try:
            with urlopen(request, timeout=90) as response:
                report["httpStatus"] = response.status
                result = CoordinationResult.model_validate(json.load(response))
        except HTTPError as error:
            report["httpStatus"] = error.code
            report["apiError"] = json.loads(error.read().decode("utf-8"))
            raise RuntimeError(f"Analysis returned HTTP {error.code}. See the saved service log.") from None
        finally:
            report["analysisSeconds"] = round(perf_counter() - request_started, 3)
        report["result"] = result.model_dump(mode="json")
        report["checks"] = check_result(result, ticket_id, database)
        if not all(report["checks"].values()):
            raise RuntimeError("The live result failed database consistency checks.")
        report["status"] = "passed"
    except Exception as error:
        report["error"] = safe_error(error)
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if log_stream is not None:
                log_stream.close()
            metrics_prefix = "Analysis completed "
            for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if metrics_prefix in line:
                    report["metrics"] = json.loads(line.split(metrics_prefix, 1)[1])
        elif log_stream is not None:
            log_stream.close()
        if client is not None:
            client.close()
        report["elapsedSeconds"] = round(perf_counter() - started, 3)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Saved report: {report_path}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
