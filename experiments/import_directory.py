"""Import fixture teams/users into paperdesk without importing evaluation tickets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import bcrypt
import dns.exception
import dns.resolver
from bson import BSON, ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from seed import FIXTURE_DIR, load_fixture, require


DATABASE_NAME = "paperdesk"
TEAM_FIELDS = ("name", "responsibilities")
USER_FIELDS = ("name", "email", "role", "isActive", "teamId")


def connection_error(error: Exception) -> str:
    """Expose the failure reason with MongoDB credentials removed."""
    uri = os.environ.get("MONGODB_URI", "")
    parsed = urlsplit(uri)
    message = str(error)
    for value in (uri, parsed.username, parsed.password):
        if value:
            message = message.replace(value, "[redacted]").replace(unquote(value), "[redacted]")
    return f"{type(error).__name__}: {message}"


def snapshot(collection: Any, session: Any = None) -> tuple[int, str]:
    """Fingerprint documents in memory; never print or save their contents."""
    digest = hashlib.sha256()
    count = 0
    for document in collection.find({}, session=session).sort("_id", 1):
        encoded = BSON.encode(document)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1
    return count, digest.hexdigest()


def preflight(database: Any, fixture: dict[str, Any], session: Any = None) -> dict[str, Any]:
    protected = []
    for first_name in ("Akrem", "Rayen"):
        matches = list(database.users.find(
            {"name": {"$regex": rf"^\s*{re.escape(first_name)}(?:\s|$)", "$options": "i"}},
            session=session,
        ))
        require(len(matches) == 1,
                f"Expected one existing {first_name} account; found {len(matches)}. No changes made.")
        protected.append(matches[0])
    fixture_user_ids = {user["_id"] for user in fixture["users"]}
    require(not any(user["_id"] in fixture_user_ids for user in protected),
            "A protected account overlaps a fixture ID. No changes made.")

    existing: dict[str, dict[ObjectId, dict[str, Any]]] = {}
    for collection_name, identity in (("teams", "name"), ("users", "email")):
        existing[collection_name] = {}
        collection = database[collection_name]
        for document in fixture[collection_name]:
            current = collection.find_one({"_id": document["_id"]}, session=session)
            if current is not None:
                require(str(current.get(identity, "")).strip().casefold()
                        == document[identity].casefold(),
                        f"{collection_name}: fixture ID {document['_id']} belongs to a different record. No changes made.")
                existing[collection_name][document["_id"]] = current
            collision = collection.find_one({
                "_id": {"$ne": document["_id"]},
                identity: {"$regex": "^" + re.escape(document[identity]) + "$", "$options": "i"},
            }, {"_id": 1}, session=session)
            require(collision is None,
                    f"{collection_name}: {document[identity]} already exists under another ID. No changes made.")
    return {"protected": protected, "existing": existing}


def plan_summary(plan: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "database": DATABASE_NAME,
        "teams_to_insert": len(fixture["teams"]) - len(plan["existing"]["teams"]),
        "users_to_insert": len(fixture["users"]) - len(plan["existing"]["users"]),
        "existing_fixture_teams": len(plan["existing"]["teams"]),
        "existing_fixture_users": len(plan["existing"]["users"]),
        "accounts_to_leave_unassigned": [
            {"id": str(user["_id"]), "name": user["name"]} for user in plan["protected"]
        ],
    }


def apply_import(database: Any, fixture: dict[str, Any], session: Any) -> dict[str, Any]:
    """Apply and verify together in a MongoDB transaction."""
    plan = preflight(database, fixture, session)
    tickets_before = snapshot(database.tickets, session)
    now = datetime.now(timezone.utc)
    counts = {}
    for collection_name, fields in (("teams", TEAM_FIELDS), ("users", USER_FIELDS)):
        inserted = updated = 0
        for document in fixture[collection_name]:
            current = plan["existing"][collection_name].get(document["_id"])
            changes = {field: document[field] for field in fields
                       if current is None or current.get(field) != document[field]}
            if not changes:
                continue
            changes["updatedAt"] = now
            insert_fields: dict[str, Any] = {"createdAt": now}
            if collection_name == "users":
                insert_fields.update({"sessionVersion": 0, "passwordHash": document["passwordHash"]})
            result = database[collection_name].update_one(
                {"_id": document["_id"]},
                {"$set": changes, "$setOnInsert": insert_fields},
                upsert=True, session=session,
            )
            inserted += int(result.upserted_id is not None)
            updated += result.modified_count
        counts[collection_name] = {"inserted": inserted, "updated": updated}

    for original in plan["protected"]:
        database.users.update_one(
            {"_id": original["_id"], "teamId": {"$ne": None}},
            {"$set": {"teamId": None, "updatedAt": now}}, session=session,
        )
        # Explicit null also handles accounts whose membership field was absent.
        database.users.update_one(
            {"_id": original["_id"], "teamId": {"$exists": False}},
            {"$set": {"teamId": None, "updatedAt": now}}, session=session,
        )
        saved = database.users.find_one({"_id": original["_id"]}, session=session)
        require(saved is not None and "teamId" in saved and saved["teamId"] is None,
                "Protected account was not left unassigned; transaction aborted.")
        preserved_fields = set(original) | set(saved)
        require(all(original.get(field) == saved.get(field)
                    for field in preserved_fields - {"teamId", "updatedAt"}),
                "Protected account changed outside membership; transaction aborted.")

    for collection_name, fields in (("teams", TEAM_FIELDS), ("users", USER_FIELDS)):
        for document in fixture[collection_name]:
            saved = database[collection_name].find_one({"_id": document["_id"]}, session=session)
            require(saved is not None and all(saved.get(field) == document[field] for field in fields),
                    f"{collection_name}: fixture verification failed; transaction aborted.")
            if collection_name == "users":
                current = plan["existing"][collection_name].get(document["_id"])
                if current is not None:
                    require(saved.get("passwordHash") == current.get("passwordHash")
                            and saved.get("sessionVersion") == current.get("sessionVersion"),
                            "Existing fixture login details changed; transaction aborted.")
                else:
                    require(saved.get("passwordHash") == document["passwordHash"],
                            "New fixture hash was not saved; transaction aborted.")
    require(snapshot(database.tickets, session) == tickets_before,
            "Ticket preservation verification failed; transaction aborted.")
    return {
        "database": DATABASE_NAME,
        **counts,
        "verified_fixture_teams": len(fixture["teams"]),
        "verified_fixture_users": len(fixture["users"]),
        "protected_accounts_preserved_and_unassigned": True,
        "tickets_preserved": tickets_before[0],
        "ticket_fingerprint_unchanged": True,
        "login_passwords_retained": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit the verified directory import. Default: read-only preflight.")
    parser.add_argument("--env-file", type=Path, default=FIXTURE_DIR.parent / "agents" / ".env")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    uri = os.environ.get("MONGODB_URI", "").strip()
    require(uri.startswith(("mongodb://", "mongodb+srv://")), "Configure MONGODB_URI in agents/.env or the environment.")
    dns_servers = [value.strip() for value in os.environ.get("MONGODB_DNS_SERVERS", "").split(",") if value.strip()]
    for server in dns_servers:
        ip_address(server)
    if uri.startswith("mongodb+srv://") and dns_servers:
        dns.resolver.get_default_resolver().nameservers = dns_servers
    fixture = load_fixture()
    with MongoClient(uri, serverSelectionTimeoutMS=10000) as client:
        client.admin.command("ping")
        database = client[DATABASE_NAME]
        plan = preflight(database, fixture)
        print(json.dumps({"stage": "preflight", **plan_summary(plan, fixture)}), flush=True)
        if not args.apply:
            print(json.dumps({"read_only": True, "tickets_present": database.tickets.count_documents({})}))
            return
        topology = client.admin.command("hello")
        require(bool(topology.get("setName") or topology.get("msg") == "isdbgrid"),
                "A replica set or sharded cluster is required for the atomic import. No changes made.")
        # Generate once outside the retriable transaction, without retaining passwords.
        for user in fixture["users"]:
            user["passwordHash"] = bcrypt.hashpw(
                secrets.token_urlsafe(32).encode("utf-8"), bcrypt.gensalt(rounds=12)
            ).decode("ascii")
        with client.start_session() as session:
            result = session.with_transaction(lambda active: apply_import(database, fixture, active))
        print(json.dumps({"stage": "committed", **result}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Directory import failed: {error}", file=sys.stderr)
        sys.exit(1)
    except (PyMongoError, dns.exception.DNSException) as error:
        print(f"Directory import failed: {connection_error(error)}", file=sys.stderr)
        sys.exit(1)
