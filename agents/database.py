"""Read the shared MongoDB collections without depending on Express."""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
import dns.resolver
from pymongo import MongoClient
from pymongo.database import Database

from .config import Settings


def create_mongo_client(settings: Settings) -> MongoClient:
    """Use the configured Atlas DNS resolvers in this Python process."""
    if settings.mongodb_uri.startswith("mongodb+srv://") and settings.mongodb_dns_servers:
        dns.resolver.get_default_resolver().nameservers = list(settings.mongodb_dns_servers)
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)


class TicketNotFoundError(LookupError):
    """The requested ticket is absent from the database."""


def serialize(value: Any) -> Any:
    """Convert MongoDB values into JSON-compatible tool results."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


class MongoDatabase:
    def __init__(self, database: Database):
        self.database = database

    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = self.database.tickets.find_one(
            {"_id": ObjectId(ticket_id)},
            {
                "_id": 1,
                "title": 1,
                "description": 1,
                "category": 1,
                "priority": 1,
                "status": 1,
                "coordination": 1,
            },
        )
        if ticket is None:
            raise TicketNotFoundError("Ticket not found.")
        return serialize(ticket)

    def list_teams(self) -> list[dict[str, Any]]:
        teams = self.database.teams.find(
            {}, {"_id": 1, "name": 1, "responsibilities": 1}
        ).sort("name", 1)
        return [serialize(team) for team in teams]

    def get_team_members(self, team_id: str) -> list[dict[str, Any]]:
        members = self.database.users.find(
            {"teamId": ObjectId(team_id), "isActive": True},
            {"_id": 1, "name": 1, "teamId": 1},
        ).sort("_id", 1)
        return [serialize(member) for member in members]
