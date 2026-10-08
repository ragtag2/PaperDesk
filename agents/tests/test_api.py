"""Check the FastAPI contract without external services."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure

from agents.agent import IncidentCoordinator
from agents.config import Settings
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
                "AGENT_MODEL_BASE_URL": "",
                "AGENT_MODEL_API_KEY": "",
                "OPENAI_API_KEY": "test-placeholder",
                "LANGFUSE_TRACING_ENABLED": "true",
            },
        ), patch("agents.main.create_mongo_client") as mongo_client, \
                patch("agents.main.AnalysisTracing.from_settings") as tracing:
            prompt = tracing.return_value.client.get_prompt.return_value
            prompt.compile.return_value = "Approved production instructions."
            prompt.version = 3
            with TestClient(create_app()) as client:
                self.assertEqual(client.get("/docs").status_code, 200)
                self.assertEqual(client.app.state.coordinator.prompt_version, "ticket-analysis-system@3")
            tracing.return_value.client.get_prompt.assert_called_once_with(
                "ticket-analysis-system", label="production", type="text",
            )
            mongo_client.return_value.close.assert_called_once()
            tracing.return_value.shutdown.assert_called_once()

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


class StartupPromptTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            mongodb_uri="mongodb://127.0.0.1:27017",
            mongodb_db_name="paperdesk",
            model="openai:test-model",
        )
        self.enterContext(patch("agents.main.Settings.from_env", return_value=self.settings))
        self.mongo = self.enterContext(patch("agents.main.create_mongo_client"))
        tracing_factory = self.enterContext(patch("agents.main.AnalysisTracing.from_settings"))
        self.tracing = tracing_factory.return_value
        self.model = self.enterContext(patch("agents.main.create_model"))
        self.coordinator = self.enterContext(patch("agents.main.IncidentCoordinator"))
        self.prompt = self.tracing.client.get_prompt.return_value
        self.prompt.compile.return_value = "Approved production instructions."
        self.prompt.version = 3
        self.coordinator.return_value.prompt_version = "ticket-analysis-system@3"
        self.coordinator.return_value.analyze.return_value = CoordinationResult(
            ticketId=TICKET_ID,
            summary="No team involvement identified.",
            relevantTeams=[],
            stakeholderUserIds=[],
        )

    def test_production_prompt_is_fetched_once_and_reused_for_requests(self):
        with TestClient(create_app()) as client:
            for _ in range(2):
                response = client.post("/analyze-ticket", json={"ticketId": TICKET_ID})
                self.assertEqual(response.status_code, 200)
        self.tracing.client.get_prompt.assert_called_once_with(
            "ticket-analysis-system", label="production", type="text",
        )
        self.prompt.compile.assert_called_once_with()
        self.model.assert_called_once_with(self.settings)
        self.coordinator.assert_called_once()
        options = self.coordinator.call_args.kwargs
        self.assertEqual(options["system_prompt"], "Approved production instructions.")
        self.assertEqual(options["prompt_version"], "ticket-analysis-system@3")
        self.assertEqual(options["model_name"], self.settings.model)
        self.assertIs(options["tracing"], self.tracing)
        self.assertEqual(self.coordinator.return_value.analyze.call_count, 2)
        self.mongo.return_value.close.assert_called_once()
        self.tracing.shutdown.assert_called_once()

    def test_missing_langfuse_client_stops_startup_and_closes_resources(self):
        self.tracing.client = None
        with self.assertRaisesRegex(RuntimeError, "Configure Langfuse"):
            with TestClient(create_app()):
                self.fail("Startup should require a Langfuse client.")
        self.model.assert_not_called()
        self.coordinator.assert_not_called()
        self.mongo.return_value.close.assert_called_once()
        self.tracing.shutdown.assert_called_once()

    def test_failed_prompt_fetch_stops_startup_and_closes_resources(self):
        self.tracing.client.get_prompt.side_effect = ConnectionError("Langfuse unavailable.")
        with self.assertRaisesRegex(ConnectionError, "Langfuse unavailable"):
            with TestClient(create_app()):
                self.fail("Startup should require the production prompt.")
        self.model.assert_not_called()
        self.coordinator.assert_not_called()
        self.mongo.return_value.close.assert_called_once()
        self.tracing.shutdown.assert_called_once()
