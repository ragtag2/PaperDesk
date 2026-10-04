"""Verify queries against the shared MongoDB storage shapes."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from bson import ObjectId

from agents.database import MongoDatabase, TicketNotFoundError


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.raw_database = MagicMock()
        self.database = MongoDatabase(self.raw_database)
        self.ticket_id = "507f1f77bcf86cd799439011"
        self.team_id = "507f1f77bcf86cd799439012"

    def test_ticket_read_includes_previous_coordination_and_serializes_ids(self):
        self.raw_database.tickets.find_one.return_value = {
            "_id": ObjectId(self.ticket_id),
            "title": "Payroll unavailable",
            "coordination": {"analyzedAt": datetime(2026, 10, 2)},
        }

        ticket = self.database.get_ticket(self.ticket_id)

        self.assertEqual(ticket["_id"], self.ticket_id)
        self.assertEqual(ticket["coordination"]["analyzedAt"], "2026-10-02T00:00:00Z")
        query, projection = self.raw_database.tickets.find_one.call_args.args
        self.assertEqual(query, {"_id": ObjectId(self.ticket_id)})
        self.assertEqual(projection["coordination"], 1)

    def test_members_query_uses_team_id_and_active_users_with_minimal_fields(self):
        self.raw_database.users.find.return_value.sort.return_value = [
            {"_id": ObjectId(self.ticket_id), "name": "Alex", "teamId": ObjectId(self.team_id)}
        ]

        members = self.database.get_team_members(self.team_id)

        self.raw_database.users.find.assert_called_once_with(
            {"teamId": ObjectId(self.team_id), "isActive": True},
            {"_id": 1, "name": 1, "teamId": 1},
        )
        self.assertEqual(members[0]["teamId"], self.team_id)

    def test_absent_ticket_raises_not_found(self):
        self.raw_database.tickets.find_one.return_value = None

        with self.assertRaises(TicketNotFoundError):
            self.database.get_ticket(self.ticket_id)
