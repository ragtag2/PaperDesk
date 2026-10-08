"""Seed the frozen evaluation CSVs into paperdesk_eval when invoked manually."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import secrets
import sys
from collections import Counter
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any

import bcrypt
import dns.exception
import dns.resolver
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient, ReplaceOne
from pymongo.errors import PyMongoError


FIXTURE_DIR = Path(__file__).resolve().parent
DATABASE_NAME = "paperdesk_eval"
CREATED_AT = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)
UPDATED_AT = datetime(2026, 10, 8, 9, tzinfo=timezone.utc)
TEAM_COLUMNS = ("_id", "name", "responsibilities")
USER_COLUMNS = ("_id", "name", "email", "role", "isActive", "teamId")
TICKET_COLUMNS = (
    "case_id", "_id", "coverage", "title", "description", "category", "priority",
    "status", "creatorId", "assigneeId", "coordination_json", "expected_answer_json",
    "required_summary_facts_json", "required_reason_facts_json", "evaluation_notes",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def text_value(value: Any, label: str, limit: int | None = None) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{label}: nonempty text required.")
    result = value.strip()
    require(limit is None or len(result) <= limit, f"{label}: text exceeds its field limit.")
    return result


def object_id(value: str) -> ObjectId:
    require(bool(re.fullmatch(r"[0-9a-f]{24}", value)), "Fixture IDs must be lowercase 24-digit hexadecimal strings.")
    return ObjectId(value)


def read_rows(filename: str, columns: tuple[str, ...], count: int) -> list[dict[str, str]]:
    with (FIXTURE_DIR / filename).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == list(columns), f"{filename}: unexpected CSV columns.")
        rows = []
        for row in reader:
            require(None not in row and all(value is not None for value in row.values()),
                    f"{filename}: a row has too many or too few CSV fields.")
            rows.append({key: value.strip() for key, value in row.items()})
    require(len(rows) == count, f"{filename}: expected {count} records.")
    ids = [str(object_id(row["_id"])) for row in rows]
    require(len(ids) == len(set(ids)), f"{filename}: duplicate IDs.")
    return rows


def string_list(value: Any, label: str) -> list[str]:
    require(isinstance(value, list), f"{label}: an array is required.")
    return [text_value(item, label) for item in value]


def validate_reference(row: dict[str, str], team_ids: set[str], users: list[dict[str, Any]]) -> None:
    """Validate the local answer key without adding it to an agent-visible document."""
    label = row["case_id"]
    expected = json.loads(row["expected_answer_json"])
    require(isinstance(expected, dict) and set(expected) == {
        "ticketId", "summary", "relevantTeams", "stakeholderUserIds",
    }, f"{label}: expected answer must follow CoordinationResult.")
    require(expected["ticketId"] == row["_id"], f"{label}: expected ticket ID differs.")
    text_value(expected["summary"], f"{label} expected summary")
    require(isinstance(expected["relevantTeams"], list), f"{label}: expected teams must be an array.")
    selected = []
    for team in expected["relevantTeams"]:
        require(isinstance(team, dict) and set(team) == {"teamId", "reason"},
                f"{label}: invalid expected team entry.")
        require(team["teamId"] in team_ids, f"{label}: unknown expected team.")
        text_value(team["reason"], f"{label} expected reason")
        selected.append(team["teamId"])
    require(len(selected) == len(set(selected)), f"{label}: duplicate expected teams.")
    stakeholder_ids = string_list(expected["stakeholderUserIds"], f"{label} expected stakeholders")
    members = {str(user["_id"]) for user in users
               if user["isActive"] and str(user["teamId"]) in selected}
    require(len(stakeholder_ids) == len(set(stakeholder_ids)) and set(stakeholder_ids) == members,
            f"{label}: expected stakeholders must be all active members of the expected teams.")
    summary_facts = string_list(json.loads(row["required_summary_facts_json"]), f"{label} summary facts")
    require(bool(summary_facts), f"{label}: summary facts are required.")
    reason_facts = json.loads(row["required_reason_facts_json"])
    require(isinstance(reason_facts, dict) and set(reason_facts) == set(selected),
            f"{label}: reason-fact keys must match expected teams.")
    for facts in reason_facts.values():
        require(bool(string_list(facts, f"{label} reason facts")), f"{label}: reason facts cannot be empty.")
    text_value(row["evaluation_notes"], f"{label} evaluation notes")


def coordination_document(value: Any, team_ids: set[str], user_ids: set[str]) -> dict[str, Any] | None:
    if value is None:
        return None
    require(isinstance(value, dict) and set(value) == {
        "summary", "relevantTeams", "stakeholderUserIds", "analyzedAt",
    }, "Previous coordination must follow the stored coordination schema.")
    require(isinstance(value["relevantTeams"], list), "Previous coordination teams must be an array.")
    teams = []
    for team in value["relevantTeams"]:
        require(isinstance(team, dict) and set(team) == {"teamId", "reason"},
                "Invalid previous coordination team entry.")
        require(team["teamId"] in team_ids, "Previous coordination references an unknown team.")
        teams.append({"teamId": object_id(team["teamId"]),
                      "reason": text_value(team["reason"], "Previous coordination reason")})
    stakeholders = string_list(value["stakeholderUserIds"], "Previous coordination stakeholders")
    require(set(stakeholders) <= user_ids, "Previous coordination references an unknown user.")
    analyzed_at = datetime.fromisoformat(text_value(value["analyzedAt"], "analyzedAt").replace("Z", "+00:00"))
    require(analyzed_at.tzinfo is not None and CREATED_AT <= analyzed_at < UPDATED_AT,
            "Previous coordination must precede the current ticket update.")
    return {
        "summary": text_value(value["summary"], "Previous coordination summary"),
        "relevantTeams": teams,
        "stakeholderUserIds": [object_id(user_id) for user_id in stakeholders],
        "analyzedAt": analyzed_at,
    }


def load_fixture() -> dict[str, list[dict[str, Any]]]:
    team_rows = read_rows("teams.csv", TEAM_COLUMNS, 6)
    user_rows = read_rows("users.csv", USER_COLUMNS, 15)
    ticket_rows = read_rows("tickets.csv", TICKET_COLUMNS, 10)
    team_ids = {row["_id"] for row in team_rows}
    user_ids = {row["_id"] for row in user_rows}
    teams = [{"_id": object_id(row["_id"]), "name": text_value(row["name"], "Team name", 120),
              "responsibilities": text_value(row["responsibilities"], "Team responsibilities", 5000),
              "createdAt": CREATED_AT, "updatedAt": UPDATED_AT} for row in team_rows]

    users = []
    for row in user_rows:
        require(row["role"] in {"employee", "support", "admin"}, "Invalid user role.")
        require(row["isActive"] in {"true", "false"}, "isActive must be true or false.")
        require(not row["teamId"] or row["teamId"] in team_ids, "Unknown user team.")
        email = row["email"].lower()
        require(bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.example", email)), "Use synthetic .example emails.")
        users.append({"_id": object_id(row["_id"]), "name": text_value(row["name"], "User name"),
                      "email": email, "role": row["role"], "isActive": row["isActive"] == "true",
                      "teamId": object_id(row["teamId"]) if row["teamId"] else None,
                      "sessionVersion": 0, "createdAt": CREATED_AT, "updatedAt": UPDATED_AT})
    require(len({user["email"] for user in users}) == len(users), "Duplicate fixture emails.")
    require(Counter(str(user["teamId"]) for user in users if user["isActive"] and user["teamId"])
            == Counter({team_id: 2 for team_id in team_ids}), "Each team needs two active members.")
    require(sum(not user["isActive"] for user in users) == 2
            and len({user["teamId"] for user in users if not user["isActive"]}) == 2
            and all(user["teamId"] is not None for user in users if not user["isActive"])
            and sum(user["isActive"] and user["teamId"] is None for user in users) == 1,
            "Expected two inactive members in different teams and one active unassigned user.")

    require(len({row["case_id"] for row in ticket_rows}) == 10, "Duplicate case identifiers.")
    require(Counter(row["coverage"] for row in ticket_rows) == Counter({
        "straightforward": 3, "cross_team": 3, "incomplete_information": 2,
        "no_relevant_team": 1, "outdated_coordination": 1,
    }), "Ticket coverage differs from the agreed ten-case mix.")
    users_by_id = {str(user["_id"]): user for user in users}
    tickets = []
    for row in ticket_rows:
        require(row["category"] in {"hardware", "software", "network", "other"}, "Invalid ticket category.")
        require(row["priority"] in {"low", "medium", "high"}, "Invalid ticket priority.")
        require(row["status"] in {"open", "in_progress", "resolved"}, "Invalid ticket status.")
        require(row["creatorId"] in user_ids and users_by_id[row["creatorId"]]["isActive"],
                "Ticket creator must be an active fixture user.")
        if row["assigneeId"]:
            assignee = users_by_id.get(row["assigneeId"])
            require(assignee is not None and assignee["isActive"] and assignee["role"] in {"support", "admin"},
                    "Ticket assignee must be active support or admin.")
        previous = coordination_document(json.loads(row["coordination_json"]), team_ids, user_ids)
        require((previous is not None) == (row["coverage"] == "outdated_coordination"),
                "Only the outdated-coordination case may contain previous coordination.")
        validate_reference(row, team_ids, users)
        # Explicitly whitelist persisted fields. No expected answers or evaluation metadata are inserted.
        tickets.append({
            "_id": object_id(row["_id"]), "title": text_value(row["title"], "Ticket title", 120),
            "description": text_value(row["description"], "Ticket description", 5000),
            "category": row["category"], "priority": row["priority"], "status": row["status"],
            "creatorId": object_id(row["creatorId"]),
            "assigneeId": object_id(row["assigneeId"]) if row["assigneeId"] else None,
            "coordination": previous, "createdAt": CREATED_AT, "updatedAt": UPDATED_AT,
        })
    return {"teams": teams, "users": users, "tickets": tickets}


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the evaluation CSVs into the fixed paperdesk_eval database.")
    parser.add_argument("--env-file", type=Path, default=FIXTURE_DIR.parent / "agents" / ".env",
                        help="Read MONGODB_URI and optional MONGODB_DNS_SERVERS here; process environment takes precedence.")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    uri = os.environ.get("MONGODB_URI", "").strip()
    require(uri.startswith(("mongodb://", "mongodb+srv://")), "Set MONGODB_URI in the environment or env file.")
    fixture = load_fixture()
    dns_servers = [server.strip() for server in os.environ.get("MONGODB_DNS_SERVERS", "").split(",") if server.strip()]
    for server in dns_servers:
        ip_address(server)
    if uri.startswith("mongodb+srv://") and dns_servers:
        dns.resolver.get_default_resolver().nameservers = dns_servers

    # MONGODB_DB_NAME and any database embedded in the URI do not select the seed destination.
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")
        database = client[DATABASE_NAME]
        for name, documents in fixture.items():
            unexpected = database[name].find_one({"_id": {"$nin": [doc["_id"] for doc in documents]}}, {"_id": 1})
            require(unexpected is None, f"{DATABASE_NAME}.{name} has records outside this fixture; use a dedicated fixture database.")
        # Satisfy the shared user schema without retaining login passwords in the fixture.
        for user in fixture["users"]:
            user["passwordHash"] = bcrypt.hashpw(secrets.token_urlsafe(32).encode("utf-8"),
                                                  bcrypt.gensalt(rounds=12)).decode("ascii")
        database.users.create_index("email", unique=True)
        database.users.create_index("teamId")
        for name, documents in fixture.items():
            database[name].bulk_write([ReplaceOne({"_id": doc["_id"]}, doc, upsert=True) for doc in documents], ordered=True)
    print(f"Seeded 6 teams, 15 users and 10 tickets in {DATABASE_NAME}.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Seed failed: {error}", file=sys.stderr)
        sys.exit(1)
    except (PyMongoError, dns.exception.DNSException):
        print("Seed failed: check MongoDB connectivity, credentials, DNS and paperdesk_eval write permissions.", file=sys.stderr)
        sys.exit(1)
