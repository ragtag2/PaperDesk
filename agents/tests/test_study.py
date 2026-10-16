"""Operator workflow and saved study provenance, using offline SDK/database inputs."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from agents.config import Settings
from agents.database import MongoDatabase, serialize
from agents.tracing import AnalysisTracing
from agents.tests import test_experiments
from agents.tests.test_variants import V3_PROMPT

from experiments import run
from experiments.run import parse_args


class StudyTests(unittest.TestCase):
    def test_variant_command_selects_study_and_pinned_v3_without_pilot_round(self):
        args = parse_args(["--dataset", "evaluation", "--study", "tools-01", "--variant", "E", "--run-name", "tools-E"])
        self.assertEqual(args.variant, "E")
        self.assertEqual(args.study, "tools-01")
        self.assertIsNone(args.round)
        self.assertEqual(args.prompt_name, "ticket-analysis-system")
        self.assertEqual(args.prompt_version, 3)

    def test_bad_variant_commands_fail_before_loading_credentials(self):
        for extra in (["--variant", "F", "--study", "s"], ["--variant", "A"],
                      ["--variant", "A", "--study", "../pilot"],
                      ["--variant", "A", "--study", "s", "--prompt-version", "4"],
                      ["--variant", "A", "--study", "s", "--round", "V3"],
                      ["--round", "V1", "--study", "s"]):
            with self.subTest(extra=extra), redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                parse_args(["--dataset", "evaluation", "--run-name", "test", *extra])

    def test_study_freezes_all_profiles_inputs_settings_and_case_identities_separately_from_pilot(self):
        fixture, cases, digest = run.load_cases()
        dataset = test_experiments.ExperimentTests.dataset(SimpleNamespace(cases=cases))
        dataset.id = "dataset-01"
        teams = serialize(fixture["teams"])
        run.prepare_dataset(dataset, cases, teams, {})
        manifest = run.study_configuration(
            Settings(mongodb_uri="mongodb://not-used", mongodb_db_name="paperdesk_eval", model="offline"),
            digest, V3_PROMPT, dataset, cases, dataset_name="evaluation", dataset_version=None,
            study="tools-01", interval_seconds=25, database=MongoDatabase({}),
        )
        with TemporaryDirectory() as folder:
            pilot = Path(folder) / "baseline.json"
            pilot.write_text('{"pilot": true}', encoding="utf-8")
            directory = Path(folder) / "studies" / "tools-01"
            run.preserve_study(directory, "A", manifest)
            run.preserve_study(directory, "E", manifest)
            saved = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(set(saved["profiles"]), set("ABCDE"))
            self.assertEqual(saved["profiles"]["E"]["tools"], [])
            self.assertEqual(saved["profiles"]["E"]["tool_schemas"], [])
            self.assertEqual(len(saved["cases"]), 30)
            self.assertEqual(saved["cases"][0]["dataset_item_id"], "dataset-item-E01")
            self.assertEqual(saved["cases"][-1]["group"], "held_out")
            self.assertEqual(pilot.read_text(encoding="utf-8"), '{"pilot": true}')
            for field, changed in (("model", "changed"), ("fixture_sha256", "changed"),
                                   ("dataset_sha256", "changed"), ("interval_seconds", 0),
                                   ("profiles", {})):
                different = deepcopy(manifest)
                different[field] = changed
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "study manifest"):
                    run.preserve_study(directory, "B", different)
            with self.assertRaisesRegex(ValueError, "variant A first"):
                run.preserve_study(Path(folder) / "fresh", "E", manifest)

    def test_check_only_freezes_without_model_construction_or_experiment_execution(self):
        from agents.tests.test_fixtures import MemoryCollection, MemoryDatabase
        fixture, cases, _ = run.load_cases()
        database = MemoryDatabase({name: MemoryCollection(documents) for name, documents in fixture.items()})
        dataset = test_experiments.ExperimentTests.dataset(SimpleNamespace(cases=cases))
        dataset.id = "dataset-01"
        dataset.run_experiment = MagicMock(side_effect=AssertionError("No live experiment allowed"))
        client = MagicMock()
        client.get_dataset.return_value = dataset
        client.get_prompt.return_value = SimpleNamespace(compile=lambda: V3_PROMPT, version=3)
        settings = Settings(mongodb_uri="mongodb://not-used", mongodb_db_name="paperdesk",
                            model="offline", langfuse_public_key="test", langfuse_secret_key="test")
        tracing = SimpleNamespace(client=client, shutdown=MagicMock())
        mongo = MagicMock()
        mongo.__enter__.return_value.__getitem__.return_value = database
        with TemporaryDirectory() as folder, \
                patch("experiments.run.REPORT_DIRECTORY", Path(folder)), \
                patch("sys.argv", ["run", "--dataset", "evaluation", "--study", "tools-01", "--variant", "A",
                                   "--run-name", "tools-A", "--check-only"]), \
                patch("experiments.run.Settings.from_env", return_value=settings), \
                patch("experiments.run.AnalysisTracing.from_settings", return_value=tracing), \
                patch("experiments.run.create_mongo_client", return_value=mongo), \
                patch("experiments.run.create_model", side_effect=AssertionError("No model allowed")):
            self.assertEqual(run.main(), 0)
            manifests = list(Path(folder).rglob("manifest.json"))
            self.assertEqual(len(manifests), 1)
            self.assertFalse(list(Path(folder).rglob("baseline.json")))
            self.assertFalse(list(Path(folder).rglob("attempt-*.json")))
        dataset.run_experiment.assert_not_called()
        client.get_prompt.assert_called_once_with("ticket-analysis-system", version=3, type="text")

    def test_reports_match_sdk_items_by_identity_and_preserve_failed_and_missing_cases(self):
        fixture, cases, _ = run.load_cases()
        dataset = test_experiments.ExperimentTests.dataset(SimpleNamespace(cases=cases))
        run.prepare_dataset(dataset, cases, serialize(fixture["teams"]), {})
        first, second = dataset.items[:2]
        first.metadata.update({"execution_status": "passed", "analysis_id": "analysis-01", "analysis_report_path": "local.json"})
        second.metadata.update({"execution_status": "failed", "execution_error": "RuntimeError: model failed"})
        output = cases[first.input["ticketId"]]["expected_answer"]
        evaluations = run.evaluate_result(input=first.input, output=output, expected_output=first.expected_output,
                                          teams=serialize(fixture["teams"]), users=serialize(fixture["users"]))
        result = SimpleNamespace(run_name="tools-A", dataset_run_url="offline", item_results=[
            SimpleNamespace(item=second, output=None, evaluations=[], trace_id="trace-02", dataset_run_id="run-01"),
            SimpleNamespace(item=first, output=output, evaluations=evaluations, trace_id="trace-01", dataset_run_id="run-01"),
        ])
        with TemporaryDirectory() as folder:
            path, incomplete = run.write_report(result, Path(folder), {"round": "A", "variant": "A", "study_id": "s"}, dataset.items)
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(incomplete)
        self.assertEqual(len(saved["cases"]), 30)
        self.assertEqual(saved["cases"][0]["dataset_item_id"], "dataset-item-E01")
        self.assertEqual(saved["cases"][0]["analysis_id"], "analysis-01")
        self.assertEqual(saved["cases"][0]["variant"], "A")
        self.assertEqual(saved["cases"][1]["execution_status"], "failed")
        self.assertEqual(saved["cases"][2]["execution_status"], "missing")
        self.assertEqual(saved["cases"][-1]["group"], "held_out")
        self.assertIsNone(saved["cases"][2]["output"])
        self.assertEqual(saved["cases"][2]["scores"], [])

    def test_task_keeps_analysis_link_and_output_when_sdk_return_is_missing(self):
        from agents.agent import IncidentCoordinator
        from agents.tests.test_fixtures import MemoryCollection, MemoryDatabase
        from agents.tests.test_variants import ObservingModel, assessment_message
        fixture, cases, _ = run.load_cases()
        database = MemoryDatabase({name: MemoryCollection(documents) for name, documents in fixture.items()})
        dataset = test_experiments.ExperimentTests.dataset(SimpleNamespace(cases=cases))
        contexts = run.prepare_dataset(dataset, cases, serialize(fixture["teams"]), {"variant": "E", "study_id": "s"})
        item = dataset.items[0]
        case = cases[item.input["ticketId"]]
        adapter = MagicMock(spec=MongoDatabase)
        adapter.get_ticket.return_value = case["ticket"]
        adapter.list_teams.return_value = serialize(fixture["teams"])
        adapter.get_team_members.return_value = [{"_id": user} for user in case["expected_answer"]["stakeholderUserIds"]]
        model = ObservingModel(responses=[assessment_message(case["expected_answer"]["relevantTeams"])])
        coordinator = IncidentCoordinator(adapter, model, variant="E", system_prompt=V3_PROMPT)
        task_records = {}
        with TemporaryDirectory() as folder, patch("agents.reporting.ANALYSES_DIRECTORY", Path(folder) / "analyses"):
            task = run.make_task(MagicMock(), coordinator, database, fixture, 0, contexts=contexts, records=task_records)
            output = task(item=item)
            self.assertEqual(task_records[item.id]["output"], output)
            self.assertEqual(item.metadata["analysis_metrics"]["modelCalls"], 1)
            self.assertIsNotNone(item.metadata["analysis_id"])
            result = SimpleNamespace(run_name="tools-E", dataset_run_url=None, item_results=[])
            path, incomplete = run.write_report(result, Path(folder), {"round": "E", "variant": "E"}, dataset.items,
                                                task_records=task_records)
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(incomplete)
        self.assertEqual(saved["cases"][0]["execution_status"], "passed")
        self.assertEqual(saved["cases"][0]["output"], output)
        self.assertEqual(saved["cases"][0]["analysis_id"], item.metadata["analysis_id"])
        self.assertIsNone(saved["cases"][0]["dataset_run_id"])
        self.assertEqual(saved["cases"][1]["execution_status"], "missing")

    def test_manual_runner_applies_variant_and_retains_interrupted_run_without_replacement(self):
        from agents.tests.test_variants import ObservingModel, assessment_message

        class Cursor(list):
            def sort(self, field, direction):
                return Cursor(sorted(self, key=lambda row: row[field], reverse=direction < 0))

        class Collection:
            def __init__(self, documents):
                self.documents = documents

            def find(self, query, fields):
                return Cursor([{key: deepcopy(row[key]) for key in fields if key in row}
                               for row in self.documents if all(row.get(key) == value for key, value in query.items())])

            def find_one(self, query, fields):
                return next(iter(self.find(query, fields)), None)

        class Database(dict):
            def __getattr__(self, name):
                return self[name]

        fixture, cases, _ = run.load_cases()
        database = Database({name: Collection(documents) for name, documents in fixture.items()})
        dataset = test_experiments.ExperimentTests.dataset(SimpleNamespace(cases=cases))
        dataset.id = "dataset-01"
        client = MagicMock()
        client.get_dataset.return_value = dataset
        client.get_prompt.return_value = SimpleNamespace(compile=lambda: V3_PROMPT, version=3)
        settings = Settings(mongodb_uri="mongodb://not-used", mongodb_db_name="paperdesk", model="offline",
                            langfuse_public_key="test", langfuse_secret_key="test")
        tracing = SimpleNamespace(client=client, shutdown=MagicMock(), analysis=AnalysisTracing().analysis)
        mongo = MagicMock()
        mongo.__enter__.return_value.__getitem__.return_value = database
        case = next(case for case in cases.values() if case["case_id"] == "E01")
        model = ObservingModel(responses=[assessment_message(case["expected_answer"]["relevantTeams"])])

        def interrupted_sdk(**kwargs):
            self.assertEqual(kwargs["max_concurrency"], 1)
            self.assertEqual(kwargs["metadata"]["variant"], "E")
            kwargs["task"](item=dataset.items[0])
            raise RuntimeError("SDK interrupted")

        dataset.run_experiment = MagicMock(side_effect=interrupted_sdk)
        command = ["run", "--dataset", "evaluation", "--study", "tools-01", "--variant", "A",
                   "--run-name", "arbitrary-label", "--interval-seconds", "0"]
        with TemporaryDirectory() as folder, redirect_stdout(StringIO()), \
                patch("experiments.run.REPORT_DIRECTORY", Path(folder) / "studies"), \
                patch("agents.reporting.ANALYSES_DIRECTORY", Path(folder) / "analyses"), \
                patch("experiments.run.Settings.from_env", return_value=settings), \
                patch("experiments.run.AnalysisTracing.from_settings", return_value=tracing), \
                patch("experiments.run.create_mongo_client", return_value=mongo), \
                patch("experiments.run.create_model", return_value=model) as model_factory:
            with patch("sys.argv", [*command, "--check-only"]):
                self.assertEqual(run.main(), 0)
            model_factory.assert_not_called()
            command[command.index("A")] = "E"
            with patch("sys.argv", command), self.assertRaisesRegex(RuntimeError, "SDK interrupted"):
                run.main()
            saved = json.loads(next((Path(folder) / "studies").rglob("E-*.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved["configuration"]["variant"], "E")
            self.assertEqual(saved["cases"][0]["execution_status"], "passed")
            self.assertIsNotNone(saved["cases"][0]["analysis_id"])
            self.assertEqual(saved["cases"][1]["execution_status"], "missing")
            self.assertEqual(len(saved["cases"]), 30)
            self.assertEqual(set(model.exposed_tools), {"TeamAssessment"})
            with patch("sys.argv", command), self.assertRaisesRegex(ValueError, "study attempt"):
                run.main()
        dataset.run_experiment.assert_called_once()
        self.assertEqual(model.position, 1)

    def test_directory_drift_during_a_preloaded_case_is_infrastructure_failure(self):
        from typing import Callable
        from agents.agent import IncidentCoordinator
        from agents.tests.test_fixtures import MemoryCollection, MemoryDatabase
        from agents.tests.test_variants import ObservingModel, assessment_message

        class MutatingModel(ObservingModel):
            mutation: Callable

            def _generate(self, *args, **kwargs):
                response = super()._generate(*args, **kwargs)
                self.mutation()
                return response

        fixture, cases, _ = run.load_cases()
        database = MemoryDatabase({name: MemoryCollection(documents) for name, documents in fixture.items()})
        dataset = test_experiments.ExperimentTests.dataset(SimpleNamespace(cases=cases))
        contexts = run.prepare_dataset(dataset, cases, serialize(fixture["teams"]), {})
        item = dataset.items[0]
        case = cases[item.input["ticketId"]]
        adapter = MagicMock(spec=MongoDatabase)
        adapter.get_ticket.return_value = case["ticket"]
        adapter.list_teams.return_value = serialize(fixture["teams"])

        def change_directory():
            next(iter(database["teams"].documents.values()))["responsibilities"] = "Changed while the model was running."

        model = MutatingModel(responses=[assessment_message([])], mutation=change_directory)
        coordinator = IncidentCoordinator(adapter, model, variant="E", system_prompt=V3_PROMPT)
        with TemporaryDirectory() as folder, patch("agents.reporting.ANALYSES_DIRECTORY", Path(folder)):
            task = run.make_task(MagicMock(), coordinator, database, fixture, 0, contexts=contexts)
            with self.assertRaises(run.FixtureMismatchError):
                task(item=item)
        self.assertEqual(item.metadata["execution_status"], "infrastructure_error")
        self.assertEqual(item.metadata["evaluation_ready"], "false")
        self.assertEqual(item.metadata["error_stage"], "post_analysis_fixture")


