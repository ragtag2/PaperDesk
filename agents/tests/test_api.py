"""Check the FastAPI contract without external services."""

from contextlib import nullcontext
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure

from agents.agent import IncidentCoordinator
from agents.config import Settings
from agents.database import MongoDatabase, TicketNotFoundError
from agents.main import create_app
from agents.schemas import CoordinationResult
from agents.tracing import AnalysisTrace, AnalysisTracing
from agents.tests.test_agent import FINANCE_ID, FINANCE_USER_ID, IT_ID, IT_USER_ID
from agents.tests.test_variants import ObservingModel, V3_PROMPT, assessment_message


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
            prompt.compile.return_value = V3_PROMPT
            prompt.version = 3
            with TestClient(create_app()) as client:
                self.assertEqual(client.get("/docs").status_code, 200)
                self.assertEqual(client.app.state.coordinator.prompt_version, "ticket-analysis-system@3")
                self.assertEqual(client.app.state.coordinator.variant.name, "E")
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
        self.coordinator.return_value.variant.name = "E"
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
        self.assertEqual(options["variant"], "E")
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


class PreloadedServiceTests(unittest.TestCase):
    def setUp(self):
        self.reports = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch("agents.reporting.ANALYSES_DIRECTORY", self.reports))
        settings = Settings(
            mongodb_uri="mongodb://127.0.0.1:27017",
            mongodb_db_name="paperdesk",
            model="openai:test-model",
        )
        self.enterContext(patch("agents.main.Settings.from_env", return_value=settings))
        self.mongo = self.enterContext(patch("agents.main.create_mongo_client"))
        self.database = MagicMock(spec=MongoDatabase)
        self.enterContext(patch("agents.main.MongoDatabase", return_value=self.database))
        self.database.get_ticket.return_value = {
            "_id": TICKET_ID, "title": "Payroll unavailable",
            "description": "Finance cannot approve salaries.",
        }
        self.database.list_teams.return_value = [
            {"_id": IT_ID, "name": "IT", "responsibilities": "Maintains applications."},
            {"_id": FINANCE_ID, "name": "Finance", "responsibilities": "Processes payroll."},
        ]
        self.database.get_team_members.side_effect = lambda team_id: [
            {"_id": IT_USER_ID if team_id == IT_ID else FINANCE_USER_ID}
        ]
        self.model_factory = self.enterContext(patch("agents.main.create_model"))
        self.tracing = MagicMock(spec=AnalysisTracing)
        self.tracing.client = MagicMock()
        self.tracing.client.get_prompt.return_value.compile.return_value = V3_PROMPT
        self.tracing.client.get_prompt.return_value.version = 3
        self.tracing.analysis.side_effect = lambda *_args: nullcontext(AnalysisTrace())
        self.enterContext(patch("agents.main.AnalysisTracing.from_settings", return_value=self.tracing))

    def test_http_analysis_uses_one_model_request_with_fresh_context_and_python_members(self):
        teams = [
            {"teamId": IT_ID, "reason": "Maintains the application."},
            {"teamId": FINANCE_ID, "reason": "Payroll is blocked."},
        ]
        model = ObservingModel(responses=[assessment_message(teams + teams[:1]), assessment_message([])])
        self.model_factory.return_value = model
        original_ticket = self.database.get_ticket.return_value
        with TestClient(create_app()) as client:
            response = client.post("/analyze-ticket", json={"ticketId": TICKET_ID})
            self.assertEqual(response.status_code, 200)
            first = response.json()
            self.assertEqual([team["teamId"] for team in first["relevantTeams"]], [IT_ID, FINANCE_ID])
            self.assertEqual(first["stakeholderUserIds"], [IT_USER_ID, FINANCE_USER_ID])
            self.assertEqual(model.position, 1)
            self.assertEqual(model.exposed_tools, ["TeamAssessment"])
            content = model.observed_messages[0][-1].content
            context = json.loads(content.split("\n\nSupplied database context:\n")[1])
            self.assertEqual(context, {"ticket": original_ticket, "teams": self.database.list_teams.return_value})
            self.assertIn("no database tools are available", model.observed_messages[0][0].content)
            self.database.get_ticket.assert_called_once_with(TICKET_ID)
            self.database.list_teams.assert_called_once_with()
            self.assertEqual(self.database.get_team_members.call_count, 2)

            updated_ticket = {
                "_id": TICKET_ID, "title": "Personal question",
                "description": "The payroll issue is resolved; this is now a personal question.",
                "coordination": first,
            }
            self.database.get_ticket.return_value = updated_ticket
            response = client.post("/analyze-ticket", json={"ticketId": TICKET_ID})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["relevantTeams"], [])
            self.assertEqual(response.json()["stakeholderUserIds"], [])
            self.assertEqual(model.position, 2)
            content = model.observed_messages[1][-1].content
            context = json.loads(content.split("\n\nSupplied database context:\n")[1])
            self.assertEqual(context["ticket"], updated_ticket)
            self.assertEqual(self.database.get_ticket.call_count, 2)
            self.assertEqual(self.database.list_teams.call_count, 2)
            self.assertEqual(self.database.get_team_members.call_count, 2)

        reports = [json.loads(path.read_text(encoding="utf-8")) for path in self.reports.rglob("*.json")]
        self.assertEqual(len(reports), 2)
        for report in reports:
            self.assertEqual(report["variant"], "E")
            self.assertEqual(report["metrics"]["modelCalls"], 1)
            self.assertEqual(report["metrics"]["toolCalls"], ["TeamAssessment"])
            self.assertTrue(all(report["checks"].values()))

    def test_missing_ticket_returns_404_before_context_or_model_requests(self):
        model = ObservingModel(responses=[])
        self.model_factory.return_value = model
        self.database.get_ticket.side_effect = TicketNotFoundError()
        with TestClient(create_app()) as client:
            response = client.post("/analyze-ticket", json={"ticketId": TICKET_ID})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"message": "Ticket not found."})
        self.assertEqual(model.position, 0)
        self.database.list_teams.assert_not_called()
        self.database.get_team_members.assert_not_called()

    def test_incompatible_production_prompt_stops_startup_and_closes_resources(self):
        model = ObservingModel(responses=[])
        self.model_factory.return_value = model
        self.tracing.client.get_prompt.return_value.compile.return_value = "Changed retrieval policy."
        with self.assertRaisesRegex(ValueError, "recognized retrieval"):
            with TestClient(create_app()):
                self.fail("An incompatible production prompt must stop startup.")
        self.assertEqual(model.position, 0)
        self.database.get_ticket.assert_not_called()
        self.mongo.return_value.close.assert_called_once()
        self.tracing.shutdown.assert_called_once()
