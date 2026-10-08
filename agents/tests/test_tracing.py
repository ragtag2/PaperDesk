"""Check real LangChain/Langfuse trace trees with an in-memory OTel exporter."""

import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from uuid import uuid4

from langfuse import Langfuse
from langchain_core.messages import AIMessage
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import get_current_span
from pymongo.errors import ConnectionFailure

from agents.agent import IncidentCoordinator
from agents.config import Settings
from agents.database import MongoDatabase, TicketNotFoundError
from agents.reporting import safe_error
from agents.tracing import AnalysisTracing, mask_exported_spans, mask_payload
from agents.tests.test_agent import (
    IT_ID, IT_USER_ID, TICKET_ID, ScriptedChatModel, scripted_responses,
)


class TracingChatModel(ScriptedChatModel):
    model_name: str = "tracing-test-model"


class FailingTracingModel(TracingChatModel):
    failure: str

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError(self.failure)


class TracingTests(unittest.TestCase):
    def setUp(self):
        self.reports = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch("agents.reporting.ANALYSES_DIRECTORY", self.reports))
        self.public_key = f"pk-lf-test-{uuid4().hex}"
        self.exporter = InMemorySpanExporter()
        self.client = Langfuse(
            public_key=self.public_key, secret_key="test-secret",
            base_url="http://localhost:3001", environment="test",
            tracer_provider=TracerProvider(), span_exporter=self.exporter,
            mask=mask_payload, mask_otel_spans=mask_exported_spans,
        )
        self.addCleanup(self.client.shutdown)
        self.tracing = AnalysisTracing(
            self.client, public_key=self.public_key,
            trace_url_template="http://localhost:3001/project/test/traces/{trace_id}",
        )
        self.database = MagicMock(spec=MongoDatabase)
        self.database.get_ticket.return_value = {
            "_id": TICKET_ID, "title": "Payroll unavailable",
            "description": "Finance cannot approve salaries.",
        }
        self.database.list_teams.return_value = [
            {"_id": IT_ID, "name": "IT", "responsibilities": "Maintains applications."},
        ]
        self.database.get_team_members.return_value = [{"_id": IT_USER_ID}]

    def coordinator(self, selected_teams=None, database=None):
        responses = scripted_responses(
            selected_teams if selected_teams is not None else [(IT_ID, "Maintains the application.")]
        )
        # Model-provided usage should reach both the existing metrics and Langfuse.
        responses = [AIMessage(
            **message.model_dump(exclude={"usage_metadata"}),
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        ) for message in responses]
        return IncidentCoordinator(
            database if database is not None else self.database,
            TracingChatModel(responses=responses), tracing=self.tracing,
        )

    def spans(self):
        self.client.flush()
        return self.exporter.get_finished_spans()

    def report(self):
        return json.loads(next(self.reports.rglob("*.json")).read_text(encoding="utf-8"))

    def test_success_includes_precheck_agent_tools_and_postprocessing_in_one_trace(self):
        coordinator = self.coordinator()
        result = coordinator.analyze(TICKET_ID)
        spans = self.spans()
        root = next(span for span in spans if span.name == "ticket-analysis")
        self.assertIsNone(root.parent)
        self.assertEqual({span.context.trace_id for span in spans}, {root.context.trace_id})
        names = [span.name for span in spans]
        self.assertEqual(names.count("get_ticket"), 2)
        self.assertEqual(names.count("list_teams"), 2)
        self.assertIn("get_team_members", names)
        self.assertIn("validate-selected-teams", names)
        self.assertIn("assemble-stakeholders", names)
        self.assertEqual(json.loads(root.attributes["langfuse.observation.output"]), result.model_dump())
        self.assertEqual(json.loads(root.attributes["langfuse.observation.input"]), {"ticketId": TICKET_ID})
        report = self.report()
        self.assertEqual(report["langfuseTraceId"], f"{root.context.trace_id:032x}")
        self.assertTrue(report["langfuseTraceUrl"].endswith(report["langfuseTraceId"]))
        self.assertEqual(report["promptVersion"], coordinator.prompt_version)
        self.assertEqual(report["metrics"]["inputTokens"], 20)
        metadata = root.attributes
        self.assertEqual(metadata["langfuse.observation.metadata.ticketId"], TICKET_ID)
        self.assertEqual(metadata["langfuse.observation.metadata.analysisId"], report["analysisId"])
        generations = [span for span in spans if span.attributes.get("langfuse.observation.type") == "generation"]
        self.assertEqual(len(generations), 2)
        self.assertEqual(sum(json.loads(span.attributes["langfuse.observation.usage_details"])["input"] for span in generations), 20)
        self.assertEqual(sum(json.loads(span.attributes["langfuse.observation.usage_details"])["output"] for span in generations), 10)
        self.assertFalse(get_current_span().get_span_context().is_valid)

    def test_missing_ticket_has_failed_trace_without_model_calls(self):
        self.database.get_ticket.side_effect = TicketNotFoundError()
        with self.assertRaises(TicketNotFoundError):
            self.coordinator().analyze(TICKET_ID)
        spans = self.spans()
        root = next(span for span in spans if span.name == "ticket-analysis")
        self.assertEqual(root.attributes["langfuse.observation.level"], "ERROR")
        self.assertFalse(any(span.attributes.get("langfuse.observation.type") == "generation" for span in spans))
        self.assertEqual(self.report()["httpStatus"], 404)
        self.assertEqual(self.report()["metrics"]["modelCalls"], 0)

    def test_unknown_team_marks_validation_and_root_failed(self):
        with self.assertRaisesRegex(ValueError, "unknown team"):
            self.coordinator([("507f1f77bcf86cd799439099", "Unknown team.")]).analyze(TICKET_ID)
        spans = self.spans()
        for name in ("ticket-analysis", "validate-selected-teams"):
            span = next(span for span in spans if span.name == name)
            self.assertEqual(span.attributes["langfuse.observation.level"], "ERROR")
        self.database.get_team_members.assert_not_called()
        self.assertEqual(self.report()["httpStatus"], 502)

    def test_database_failure_keeps_503_and_redacts_configured_secrets(self):
        secret = "tracing-test-canary-secret"
        self.enterContext(patch.dict("os.environ", {"LANGFUSE_SECRET_KEY": secret}))
        self.database.get_ticket.side_effect = ConnectionFailure(f"Failed with {secret}")
        with self.assertRaises(ConnectionFailure):
            self.coordinator().analyze(TICKET_ID)
        serialized = "\n".join(span.to_json() for span in self.spans())
        self.assertNotIn(secret, serialized)
        report = self.report()
        self.assertNotIn(secret, json.dumps(report))
        self.assertIn("[redacted]", report["error"])
        self.assertEqual(report["httpStatus"], 503)
        self.assertNotIn(secret, safe_error(ValueError(secret)))

    def test_concurrent_analyses_have_distinct_roots_and_matching_report_ids(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: self.coordinator().analyze(TICKET_ID), range(2)))
        self.assertEqual(len(results), 2)
        spans = self.spans()
        roots = [span for span in spans if span.name == "ticket-analysis"]
        root_ids = {span.context.trace_id for span in roots}
        self.assertEqual(len(root_ids), 2)
        self.assertTrue(all(span.context.trace_id in root_ids for span in spans))
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in self.reports.rglob("*.json")]
        self.assertEqual({report["langfuseTraceId"] for report in reports}, {f"{trace_id:032x}" for trace_id in root_ids})
        self.assertEqual(len({report["analysisId"] for report in reports}), 2)
        self.assertFalse(get_current_span().get_span_context().is_valid)

    def test_model_failure_records_failed_generation_and_preserves_redacted_report(self):
        secret = "model-failure-canary-secret"
        self.enterContext(patch.dict("os.environ", {"GROQ_API_KEY": secret}))
        coordinator = IncidentCoordinator(
            self.database, FailingTracingModel(responses=[], failure=f"Provider failed with {secret}"),
            tracing=self.tracing,
        )
        with self.assertRaises(RuntimeError):
            coordinator.analyze(TICKET_ID)
        spans = self.spans()
        generations = [span for span in spans if span.attributes.get("langfuse.observation.type") == "generation"]
        self.assertEqual(len(generations), 1)
        self.assertEqual(generations[0].attributes["langfuse.observation.level"], "ERROR")
        self.assertNotIn(secret, "\n".join(span.to_json() for span in spans))
        report = self.report()
        self.assertEqual(report["httpStatus"], 502)
        self.assertEqual(report["metrics"]["modelCalls"], 1)
        self.assertEqual(report["metrics"]["modelRequests"][0]["status"], "failed")
        self.assertNotIn(secret, json.dumps(report))

    def test_export_failure_does_not_discard_coordination_or_local_metrics(self):
        with patch.object(self.exporter, "export", return_value=SpanExportResult.FAILURE) as export:
            result = self.coordinator().analyze(TICKET_ID)
            self.client.flush()
            export.assert_called()
        self.assertEqual(result.stakeholderUserIds, [IT_USER_ID])
        report = self.report()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["metrics"]["modelCalls"], 2)

    def test_observation_creation_failure_preserves_success_and_local_report(self):
        with patch.object(self.client, "start_as_current_observation", side_effect=RuntimeError("Tracer unavailable")):
            result = self.coordinator().analyze(TICKET_ID)
        self.assertEqual(result.stakeholderUserIds, [IT_USER_ID])
        report = self.report()
        self.assertEqual(report["status"], "passed")
        self.assertNotIn("langfuseTraceId", report)

    def test_disabled_or_unconfigured_tracing_never_initializes_client(self):
        for settings in (
            Settings("mongodb://localhost", "test", "test-model"),
            Settings("mongodb://localhost", "test", "test-model", langfuse_public_key="public"),
            Settings("mongodb://localhost", "test", "test-model", langfuse_public_key="public",
                     langfuse_secret_key="secret", langfuse_tracing_enabled=False),
        ):
            with self.subTest(settings=settings), patch("agents.tracing.Langfuse") as client:
                self.assertIsNone(AnalysisTracing.from_settings(settings).client)
                client.assert_not_called()

    def test_endpoint_lookup_failure_keeps_tracing_client_available(self):
        settings = Settings("mongodb://localhost", "test", "test-model",
                            langfuse_public_key="public", langfuse_secret_key="secret")
        with patch("agents.tracing.Langfuse") as client:
            client.return_value.get_trace_url.side_effect = ConnectionError("Langfuse unreachable")
            tracing = AnalysisTracing.from_settings(settings)
        self.assertIs(tracing.client, client.return_value)
        self.assertIsNone(tracing.trace_url_template)
        with patch.object(self.client, "shutdown", side_effect=ConnectionError("Langfuse unreachable")):
            self.tracing.shutdown()
