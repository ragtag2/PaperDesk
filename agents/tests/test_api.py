"""Check the FastAPI contract without external services."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure

from agents.agent import IncidentCoordinator
from agents.database import TicketNotFoundError
from agents.main import create_app
from agents.schemas import CoordinationResult


TICKET_ID = "507f1f77bcf86cd799439011"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = MagicMock(spec=IncidentCoordinator)
        self.coordinator.analyze.return_value = CoordinationResult(
            ticketId=TICKET_ID,
            summary="No team involvement identified.",
            relevantTeams=[],
            stakeholderUserIds=[],
        )
        self.client = self.enterContext(TestClient(create_app(self.coordinator)))

    def test_request_requires_only_ticket_id_and_returns_coordination(self):
        response = self.client.post("/analyze-ticket", json={"ticketId": TICKET_ID})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.coordinator.analyze.return_value.model_dump())
        self.coordinator.analyze.assert_called_once_with(TICKET_ID)

    def test_openapi_matches_documented_request_and_error_responses(self):
        schema = self.client.get("/openapi.json").json()
        request = schema["components"]["schemas"]["AnalyzeTicketRequest"]
        responses = schema["paths"]["/analyze-ticket"]["post"]["responses"]

        self.assertEqual(set(request["properties"]), {"ticketId"})
        self.assertTrue({"200", "400", "404", "502", "503"}.issubset(responses))
        self.assertNotIn("422", responses)

    def test_default_lifespan_builds_model_adapter_and_closes_database(self):
        # Initialize the real adapter, but do not make model or database requests.
        with patch.dict(
            "os.environ",
            {
                "MONGODB_URI": "mongodb://127.0.0.1:27017",
                "MONGODB_DB_NAME": "paperdesk",
                "AGENT_MODEL": "openai:test-model",
                "OPENAI_API_KEY": "test-placeholder",
            },
        ), patch("agents.main.MongoClient") as mongo_client:
            with TestClient(create_app()) as client:
                self.assertEqual(client.get("/docs").status_code, 200)
            mongo_client.return_value.close.assert_called_once()

    def test_invalid_input_uses_contract_error_format(self):
        for body in [{"ticketId": "invalid"}, {"ticketId": TICKET_ID, "teams": []}]:
            with self.subTest(body=body):
                response = self.client.post("/analyze-ticket", json=body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(set(response.json()), {"message"})
        self.coordinator.analyze.assert_not_called()

    def test_missing_ticket_returns_404(self):
        self.coordinator.analyze.side_effect = TicketNotFoundError()

        response = self.client.post("/analyze-ticket", json={"ticketId": TICKET_ID})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"message": "Ticket not found."})

    def test_database_connection_failure_returns_503(self):
        self.coordinator.analyze.side_effect = ConnectionFailure()

        response = self.client.post("/analyze-ticket", json={"ticketId": TICKET_ID})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"message": "Database unavailable."})
