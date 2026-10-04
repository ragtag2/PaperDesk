"""The three MongoDB read capabilities available to LangChain."""

from typing import Any

from langchain.tools import tool
from langchain_core.tools import BaseTool

from .database import MongoDatabase


def create_database_tools(database: MongoDatabase) -> list[BaseTool]:
    @tool
    def get_ticket(ticket_id: str) -> dict[str, Any]:
        """Read a ticket's details and previous coordination result by its ID."""
        return database.get_ticket(ticket_id)

    @tool
    def list_teams() -> list[dict[str, Any]]:
        """Read all team IDs, names, and responsibility descriptions."""
        return database.list_teams()

    @tool
    def get_team_members(team_id: str) -> list[dict[str, Any]]:
        """Read the IDs and names of active users belonging to this team."""
        return database.get_team_members(team_id)

    return [get_ticket, list_teams, get_team_members]
