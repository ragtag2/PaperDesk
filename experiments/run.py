"""Manually run one frozen, full-agent evaluation round through Langfuse.

No database writes, seed invocation, judge calls or prompt revisions occur here.
The configured Langfuse rules score completed paperdesk-eval-case observations.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import perf_counter, sleep
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

# Support both `python -m experiments.run` and `python experiments/run.py`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.agent import IncidentCoordinator, SYSTEM_PROMPT
from agents.config import Settings
from agents.database import MongoDatabase, TicketNotFoundError, create_mongo_client, serialize
from agents.model import create_model
from agents.reporting import safe_error
from agents.schemas import AnalyzeTicketRequest
from agents.tracing import AnalysisTracing
from experiments.evaluators import SCORE_NAMES, evaluate_result, reference_answer
from experiments.seed import DATABASE_NAME, FIXTURE_DIR, TICKET_COLUMNS, load_fixture, read_rows


OBSERVATION_NAME = "paperdesk-eval-case"
REPORT_DIRECTORY = FIXTURE_DIR.parent / "agents" / "runs" / "experiments"
TICKET_TOOL_FIELDS = ("_id", "title", "description", "category", "priority", "status", "coordination")
FIXED_CODE_FILES = (
    "agents/agent.py", "agents/config.py", "agents/database.py", "agents/model.py",
    "agents/tools.py", "agents/schemas.py", "agents/tracing.py", "agents/reporting.py",
    "agents/requirements.txt", "experiments/run.py", "experiments/evaluators.py",
    "experiments/seed.py", "experiments/EVALUATION_RULES.md", "experiments/requirements.txt",
)


class FixtureMismatchError(RuntimeError):
    """Agent-visible database data differs from the frozen evaluation fixtures."""


def canonical_records(documents: list[dict]) -> list[dict]:
    return sorted(serialize(documents), key=lambda document: document["_id"])


def load_cases() -> tuple[dict, dict[str, dict], str]:
    # Reuse the seeder's validation and document conversion, without calling main().
    fixture = load_fixture()
    rows = read_rows("tickets.csv", TICKET_COLUMNS, 10)
    tickets = {str(ticket["_id"]): serialize(ticket) for ticket in fixture["tickets"]}
    cases = {}
    for row in rows:
        cases[row["_id"]] = {
            "case_id": row["case_id"], "coverage": row["coverage"],
            "ticket": {field: tickets[row["_id"]][field] for field in TICKET_TOOL_FIELDS},
            "required_summary_facts": json.loads(row["required_summary_facts_json"]),
            "required_reason_facts": json.loads(row["required_reason_facts_json"]),
            "expected_answer": reference_answer(json.loads(row["expected_answer_json"])),
            "evaluation_notes": row["evaluation_notes"],
        }
    content = {filename: (FIXTURE_DIR / filename).read_text(encoding="utf-8-sig")
               for filename in ("teams.csv", "users.csv", "tickets.csv")}
    digest = sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()
    return fixture, cases, digest


def check_database(database, fixture: dict) -> None:
    for collection, documents in fixture.items():
        fields = {key: 1 for key in documents[0]}
        actual = list(database[collection].find({}, fields))
        if canonical_records(actual) != canonical_records(documents):
            raise FixtureMismatchError(
                f"{DATABASE_NAME}.{collection} differs from the CSV fixture. "
                "Restore the intended fixture before running an experiment."
            )


class FrozenMongoDatabase(MongoDatabase):
    """Use the real MongoDB tools, checking their results against frozen inputs."""

    def __init__(self, database, fixture: dict, cases: dict[str, dict]):
        super().__init__(database)
        self.cases = cases
        self.teams = [{field: serialize(team[field]) for field in ("_id", "name", "responsibilities")}
                      for team in fixture["teams"]]
        self.users = serialize(fixture["users"])

    def get_ticket(self, ticket_id: str) -> dict:
        try:
            actual = super().get_ticket(ticket_id)
        except TicketNotFoundError as error:
            raise FixtureMismatchError("A frozen fixture ticket is no longer available.") from error
        case = self.cases.get(ticket_id.lower())
        if case is None or actual != case["ticket"]:
            raise FixtureMismatchError("A ticket tool result differs from the frozen case.")
        return actual

    def list_teams(self) -> list[dict]:
        actual = super().list_teams()
        if canonical_records(actual) != canonical_records(self.teams):
            raise FixtureMismatchError("The team directory changed during the experiment.")
        return actual

    def get_team_members(self, team_id: str) -> list[dict]:
        actual = super().get_team_members(team_id)
        expected = [{field: user[field] for field in ("_id", "name", "teamId")}
                    for user in self.users if user["isActive"] and user["teamId"] == team_id.lower()]
        if canonical_records(actual) != canonical_records(expected):
            raise FixtureMismatchError("Active team membership changed during the experiment.")
        return actual


def build_evaluation_context(case: dict, teams: list[dict], run_metadata: dict) -> dict:
    return {
        **deepcopy(case), "teams": deepcopy(teams), **run_metadata,
        "evaluation_ready": "false", "reason_applicable": "false",
    }


def canonical_answer(value: Any) -> dict:
    if isinstance(value, str):
        value = json.loads(value)
    answer = reference_answer(value)
    answer["ticketId"] = answer["ticketId"].lower()
    for team in answer["relevantTeams"]:
        team["teamId"] = team["teamId"].lower()
    answer["relevantTeams"].sort(key=lambda team: team["teamId"])
    answer["stakeholderUserIds"] = sorted(user_id.lower() for user_id in answer["stakeholderUserIds"])
    return answer


def dataset_request(value: Any, item_id: str) -> AnalyzeTicketRequest:
    message = (
        f"Dataset item {item_id}: Input must be an object like "
        '{"ticketId": "300000000000000000000007"} or a bare 24-character ticket ID. '
        "Copy the complete ID from tickets.csv and keep it as a quoted string."
    )
    if isinstance(value, str):
        value = value.strip()
        # All-digit ObjectIds are identifiers, not JSON numbers. Preserve every
        # character before attempting JSON decoding (including leading zeros).
        if re.fullmatch(r"[0-9a-fA-F]{24}", value):
            value = {"ticketId": value}
        else:
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                raise ValueError(message) from error
    if isinstance(value, str):
        value = {"ticketId": value.strip()}
    elif type(value) is int:
        # Exact integers can be recovered; floats and booleans cannot be IDs.
        # prepare_dataset additionally requires an exact, known fixture ID.
        value = {"ticketId": str(value)}
    try:
        return AnalyzeTicketRequest.model_validate(value, strict=True)
    except ValidationError as error:
        raise ValueError(message) from error


def prepare_dataset(dataset, cases: dict[str, dict], teams: list[dict], run_metadata: dict) -> dict[str, dict]:
    active = [item for item in dataset.items if item.status == "ACTIVE"]
    seen = set()
    prepared = []
    contexts = {}
    for item in active:
        request = dataset_request(item.input, item.id)
        ticket_id = request.ticketId.lower()
        if ticket_id not in cases:
            raise ValueError(
                f"Dataset item {item.id}: unknown ticket ID {ticket_id!r}. "
                "Copy the exact 24-character ID from tickets.csv as a quoted string."
            )
        if ticket_id in seen:
            raise ValueError(f"Dataset item {item.id}: duplicate ticket ID {ticket_id!r}.")
        case = cases[ticket_id]
        if item.expected_output is not None and canonical_answer(item.expected_output) != canonical_answer(case["expected_answer"]):
            raise ValueError(f"{case['case_id']}: dataset expected output differs from tickets.csv.")
        seen.add(ticket_id)
        contexts[ticket_id] = build_evaluation_context(case, teams, run_metadata)
        # SDK DatasetItem models are frozen. Copy them locally, preserving the
        # dataset/item IDs for SDK linkage; no dataset creation/update API is called.
        prepared.append(item.model_copy(update={
            "input": {"ticketId": ticket_id},
            "expected_output": deepcopy(case["expected_answer"]),
            # The SDK propagates item metadata with a 200-character value limit.
            # Keep references here; make_task writes the full context directly
            # after the SDK has captured these small propagation attributes.
            "metadata": {"case_id": case["case_id"], "coverage": case["coverage"],
                         "evaluation_ready": "false", "reason_applicable": "false"},
        }))
    if seen != set(cases):
        raise ValueError("The dataset must contain exactly the ten active fixture tickets.")
    dataset.items = sorted(prepared, key=lambda item: item.metadata["case_id"])
    return contexts


def select_prompt(client, args) -> tuple[str, str, dict]:
    if args.prompt_name is None:
        if args.round != "V1" or args.prompt_version is not None:
            raise ValueError("V2 and V3 require --prompt-name and --prompt-version.")
        instructions = SYSTEM_PROMPT
        prompt_id = sha256(instructions.encode("utf-8")).hexdigest()
        return instructions, prompt_id, {"prompt_source": "builtin", "prompt_version": prompt_id}
    if args.prompt_version is None or args.prompt_version < 1:
        raise ValueError("Provide a positive --prompt-version with --prompt-name.")
    prompt = client.get_prompt(args.prompt_name, version=args.prompt_version, type="text")
    instructions = prompt.compile()
    if not isinstance(instructions, str) or not instructions.strip() or "{{" in instructions:
        raise ValueError("Use a nonempty text system prompt with no unresolved variables.")
    if args.round == "V1" and instructions != SYSTEM_PROMPT:
        raise ValueError("V1 must use SYSTEM_PROMPT exactly. Omit prompt options to use the builtin baseline.")
    prompt_id = f"{args.prompt_name}@{prompt.version}"
    return instructions, prompt_id, {
        "prompt_source": "langfuse", "prompt_name": args.prompt_name,
        "prompt_version": prompt.version,
    }


def fixed_configuration(settings: Settings, fixture_hash: str) -> dict:
    root = FIXTURE_DIR.parent
    source_hash = sha256(json.dumps(
        {filename: (root / filename).read_text(encoding="utf-8-sig") for filename in FIXED_CODE_FILES},
        sort_keys=True,
    ).encode("utf-8")).hexdigest()
    return {
        "database": DATABASE_NAME, "fixture_sha256": fixture_hash, "source_sha256": source_hash,
        "model": settings.model, "temperature": 0,
        "model_base_url": settings.model_base_url,
        "model_timeout_seconds": settings.model_timeout_seconds,
        "model_max_tokens": settings.model_max_tokens, "model_max_retries": 0,
        "packages": {name: version(name) for name in (
            "langfuse", "langchain", "langchain-core", "langchain-groq", "langchain-openai",
            "pydantic", "pymongo",
        )},
    }


def preserve_baseline(directory: Path, round_name: str, configuration: dict) -> None:
    path = directory / "baseline.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != configuration:
            raise ValueError("Fixtures, code, packages or model settings differ from the recorded V1 baseline.")
    elif round_name != "V1":
        raise ValueError("Run V1 first to record the fixed configuration.")
    else:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")


def make_task(client, coordinator, database, fixture: dict, interval_seconds: float,
              *, contexts: dict[str, dict] | None = None):
    last_started = None

    def task(*, item, **_kwargs):
        nonlocal last_started
        metadata = item.metadata
        if contexts is not None:
            metadata.update(deepcopy(contexts[item.input["ticketId"]]))
        client.update_current_span(
            name=OBSERVATION_NAME, version=coordinator.prompt_version, metadata=metadata,
        )
        # Infrastructure/fixture failures are raised, so the SDK records an error
        # without converting them into model-quality scores.
        try:
            check_database(database, fixture)
        except Exception as error:
            metadata.update({"infrastructure_error": safe_error(error), "execution_status": "infrastructure_error"})
            client.update_current_span(metadata=metadata, level="ERROR", status_message=safe_error(error))
            raise
        if last_started is not None:
            sleep(max(0, interval_seconds - (perf_counter() - last_started)))
        last_started = perf_counter()
        started = perf_counter()
        result = None
        try:
            result = coordinator.analyze(item.input["ticketId"]).model_dump(mode="json")
        except FixtureMismatchError as error:
            metadata["infrastructure_error"] = safe_error(error)
            client.update_current_span(metadata=metadata, level="ERROR", status_message=safe_error(error))
            raise
        except Exception as error:
            # Returning None lets the SDK run all five deterministic checks even
            # for failed analyses; nonexistent outputs are ineligible for judges.
            metadata["execution_error"] = safe_error(error)
        finally:
            metadata["analysis_seconds"] = round(perf_counter() - started, 3)
            metadata["execution_status"] = (
                "infrastructure_error" if "infrastructure_error" in metadata
                else "passed" if result is not None else "failed"
            )
            metadata["evaluation_ready"] = "true" if result is not None else "false"
            metadata["reason_applicable"] = "true" if result is not None and (
                result["relevantTeams"] or metadata["expected_answer"]["relevantTeams"]
            ) else "false"
            client.update_current_span(
                metadata=metadata, output=result,
                level="DEFAULT" if result is not None else "ERROR",
                status_message=metadata.get("execution_error") or metadata.get("infrastructure_error"),
            )
        return result

    return task


def write_report(result, directory: Path, run_metadata: dict, items: list) -> tuple[Path, bool]:
    expected_count = len(items)
    records = []
    for item_result in result.item_results:
        records.append({
            "case_id": item_result.item.metadata["case_id"],
            "input": item_result.item.input, "metadata": item_result.item.metadata,
            "output": item_result.output, "trace_id": item_result.trace_id,
            "dataset_run_id": item_result.dataset_run_id,
            "scores": [{"name": evaluation.name, "value": evaluation.value,
                        "comment": evaluation.comment, "details": evaluation.metadata}
                       for evaluation in item_result.evaluations],
        })
    completed = {record["case_id"] for record in records}
    for item in items:
        if item.metadata["case_id"] not in completed:
            records.append({
                "case_id": item.metadata["case_id"], "input": item.input, "metadata": item.metadata,
                "output": None, "trace_id": None, "dataset_run_id": None, "scores": [],
                "sdk_task_error": item.metadata.get("infrastructure_error") or "The SDK did not return this case.",
            })
    records.sort(key=lambda record: record["case_id"])
    incomplete = len(completed) != expected_count or any(
        {evaluation["name"] for evaluation in record["scores"]} != set(SCORE_NAMES)
        or record["dataset_run_id"] is None or record["output"] is None
        for record in records
    )
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{run_metadata['round']}-{stamp}-{uuid4().hex[:8]}.json"
    path.write_text(json.dumps({
        "run_name": result.run_name, "dataset_run_url": result.dataset_run_url,
        "configuration": run_metadata, "expected_case_count": expected_count,
        "completed_sdk_case_count": len(completed), "execution_or_evaluation_errors": incomplete,
        "llm_judges": "Managed asynchronously by Langfuse rules; not included in this report.",
        "cases": records,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name in SCORE_NAMES:
        values = [evaluation["value"] for record in records for evaluation in record["scores"]
                  if evaluation["name"] == name]
        print(f"{name}: {sum(value == 1 for value in values)}/{expected_count} pass; {len(values)} scored")
    return path, incomplete


def parse_args():
    parser = argparse.ArgumentParser(description="Run one full-agent round against the fixed paperdesk_eval fixture.")
    parser.add_argument("--dataset", required=True, help="Name of the existing Langfuse dataset with ten fixture items.")
    parser.add_argument("--round", required=True, choices=("V1", "V2", "V3"))
    parser.add_argument("--run-name", required=True, help="A unique dataset run name, for example paperdesk-V1.")
    parser.add_argument("--prompt-name", help="Langfuse text prompt name; omit for V1's builtin baseline.")
    parser.add_argument("--prompt-version", type=int, help="Pinned numeric version; required with --prompt-name.")
    parser.add_argument("--dataset-version", help="Optional frozen dataset timestamp, such as 2026-10-08T20:00:00Z.")
    parser.add_argument("--interval-seconds", type=float, default=25,
                        help="Minimum time between case starts (default 25); no automatic model retries.")
    args = parser.parse_args()
    if not args.dataset.strip() or not args.run_name.strip():
        parser.error("Dataset and run names must be nonempty.")
    if not math.isfinite(args.interval_seconds) or args.interval_seconds < 0:
        parser.error("--interval-seconds must be finite and nonnegative.")
    return args


def main() -> int:
    args = parse_args()
    fixture, cases, fixture_hash = load_cases()
    settings = replace(Settings.from_env(), mongodb_db_name=DATABASE_NAME)
    if not settings.langfuse_tracing_enabled or not settings.langfuse_public_key or not settings.langfuse_secret_key:
        raise ValueError("Enable Langfuse tracing and configure both keys in agents/.env.")
    tracing = AnalysisTracing.from_settings(settings)
    if tracing.client is None:
        raise ValueError("Langfuse initialization failed.")
    client = tracing.client
    try:
        instructions, prompt_id, prompt_metadata = select_prompt(client, args)
        dataset_version = None
        if args.dataset_version:
            dataset_version = datetime.fromisoformat(args.dataset_version.replace("Z", "+00:00"))
            if dataset_version.tzinfo is None:
                raise ValueError("--dataset-version must include a timezone.")
            dataset_version = dataset_version.astimezone(timezone.utc)
        dataset = client.get_dataset(args.dataset, version=dataset_version)
        configuration = fixed_configuration(settings, fixture_hash)
        run_metadata = {
            **configuration, **prompt_metadata, "round": args.round,
            "prompt_sha256": sha256(instructions.encode("utf-8")).hexdigest(),
            "dataset_name": args.dataset, "dataset_version": dataset_version.isoformat() if dataset_version else None,
            "interval_seconds": args.interval_seconds,
        }
        teams = [{key: serialize(team[key]) for key in ("_id", "name", "responsibilities")}
                 for team in fixture["teams"]]
        contexts = prepare_dataset(dataset, cases, teams, run_metadata)
        directory = REPORT_DIRECTORY / sha256(dataset.id.encode("utf-8")).hexdigest()[:16]
        with create_mongo_client(settings) as mongo:
            database = mongo[DATABASE_NAME]
            check_database(database, fixture)
            preserve_baseline(directory, args.round, configuration)
            coordinator = IncidentCoordinator(
                FrozenMongoDatabase(database, fixture, cases), create_model(settings),
                model_name=settings.model, tracing=tracing,
                system_prompt=instructions, prompt_version=prompt_id,
            )

            def deterministic_checks(**values):
                return evaluate_result(**values, teams=teams, users=serialize(fixture["users"]))

            result = dataset.run_experiment(
                name="Paperdesk ticket coordination", run_name=args.run_name,
                description=f"{args.round}: ten frozen full-agent cases; review before the next round.",
                task=make_task(client, coordinator, database, fixture, args.interval_seconds, contexts=contexts),
                evaluators=[deterministic_checks], max_concurrency=1, metadata=run_metadata,
            )
            path, incomplete = write_report(result, directory, run_metadata, dataset.items)
            print(f"Local report: {path}")
            if result.dataset_run_url:
                print(f"Langfuse experiment: {result.dataset_run_url}")
            print("LLM judges run separately through your Langfuse rules.")
            return 1 if incomplete else 0
    finally:
        tracing.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Experiment failed: {safe_error(error)}", file=sys.stderr)
        sys.exit(1)
