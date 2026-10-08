"""Prepared offline checks for evaluation correctness and judge eligibility.

Running these tests is user-managed; no live model, MongoDB or Langfuse is needed.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from langfuse.api import DatasetItem

from agents.database import serialize
from agents.schemas import CoordinationResult
from experiments.evaluators import evaluate_result
from experiments.run import (
    FixtureMismatchError, build_evaluation_context, dataset_request, load_cases,
    make_task, prepare_dataset,
)


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture, cls.cases, _digest = load_cases()
        cls.teams = serialize(fixture["teams"])
        cls.users = serialize(fixture["users"])

    def check_scores(self, ticket_id, output):
        return {evaluation.name: evaluation.value for evaluation in evaluate_result(
            input={"ticketId": ticket_id}, output=output,
            expected_output=self.cases[ticket_id]["expected_answer"],
            teams=self.teams, users=self.users,
        )}

    def test_all_reference_answers_pass_including_empty_selection(self):
        for ticket_id, case in self.cases.items():
            with self.subTest(case=case["case_id"]):
                scores = self.check_scores(ticket_id, deepcopy(case["expected_answer"]))
                self.assertEqual(set(scores.values()), {1})

    def test_failed_execution_never_passes_even_for_empty_reference(self):
        ticket_id = next(key for key, case in self.cases.items() if case["case_id"] == "E09")
        self.assertEqual(set(self.check_scores(ticket_id, None).values()), {0})

    def test_wrong_team_selection_can_have_valid_assembled_membership(self):
        by_case = {case["case_id"]: (ticket_id, case) for ticket_id, case in self.cases.items()}
        ticket_id, case = by_case["E01"]
        output = deepcopy(case["expected_answer"])
        extra = by_case["E03"][1]["expected_answer"]
        output["relevantTeams"].extend(deepcopy(extra["relevantTeams"]))
        output["stakeholderUserIds"].extend(extra["stakeholderUserIds"])
        scores = self.check_scores(ticket_id, output)
        self.assertEqual(scores["team_exact_match"], 0)
        self.assertEqual(scores["stakeholder_expected_match"], 0)
        self.assertEqual(scores["stakeholders_match_selected_teams"], 1)
        self.assertEqual(scores["application_valid"], 1)

    def test_inactive_and_unassigned_users_are_excluded(self):
        ticket_id, case = next(iter(self.cases.items()))
        for user in self.users:
            if user["isActive"] and user["teamId"] is not None:
                continue
            with self.subTest(user=user["_id"]):
                output = deepcopy(case["expected_answer"])
                output["stakeholderUserIds"].append(user["_id"])
                scores = self.check_scores(ticket_id, output)
                self.assertEqual(scores["stakeholder_expected_match"], 0)
                self.assertEqual(scores["stakeholders_match_selected_teams"], 0)
                self.assertEqual(scores["application_valid"], 0)

    def test_duplicates_fail_validity_even_when_sets_match(self):
        ticket_id, case = next(iter(self.cases.items()))
        output = deepcopy(case["expected_answer"])
        output["relevantTeams"].append(deepcopy(output["relevantTeams"][0]))
        output["stakeholderUserIds"].append(output["stakeholderUserIds"][0])
        scores = self.check_scores(ticket_id, output)
        self.assertEqual(scores["team_exact_match"], 1)
        self.assertEqual(scores["stakeholder_expected_match"], 1)
        self.assertEqual(scores["application_valid"], 0)

    def test_schema_failures_are_separate_from_set_correctness(self):
        ticket_id, case = next(iter(self.cases.items()))
        output = deepcopy(case["expected_answer"])
        output["unexpected"] = "field"
        scores = self.check_scores(ticket_id, output)
        self.assertEqual(scores["application_valid"], 0)
        self.assertEqual(scores["team_exact_match"], 1)

    def test_ids_are_compared_case_insensitively(self):
        ticket_id, team_id, user_id = "a" * 24, "b" * 24, "c" * 24
        reference = {"ticketId": ticket_id, "summary": "An incident.",
                     "relevantTeams": [{"teamId": team_id, "reason": "Owns the issue."}],
                     "stakeholderUserIds": [user_id]}
        output = deepcopy(reference)
        output["ticketId"] = ticket_id.upper()
        output["relevantTeams"][0]["teamId"] = team_id.upper()
        output["stakeholderUserIds"] = [user_id.upper()]
        scores = evaluate_result(input={"ticketId": ticket_id}, output=output, expected_output=reference,
                                 teams=[{"_id": team_id}],
                                 users=[{"_id": user_id, "teamId": team_id, "isActive": True}])
        self.assertTrue(all(evaluation.value == 1 for evaluation in scores))

    def test_bad_reference_raises_instead_of_becoming_agent_score_zero(self):
        with self.assertRaises(ValidationError):
            evaluate_result(input={"ticketId": "a" * 24}, output=None, expected_output=None,
                            teams=self.teams, users=self.users)

    def dataset(self):
        now = datetime(2026, 10, 8, tzinfo=timezone.utc)
        return SimpleNamespace(items=[DatasetItem(
            id=f"dataset-item-{case['case_id']}", status="ACTIVE",
            input=json.dumps({"ticketId": ticket_id}), expected_output=None, metadata=None,
            dataset_id="fixture-dataset", dataset_name="fixture-dataset",
            created_at=now, updated_at=now, media_references=[],
        ) for ticket_id, case in self.cases.items()])

    def test_dataset_context_is_built_from_csv_and_is_independent(self):
        dataset = self.dataset()
        original = dataset.items[0]
        contexts = prepare_dataset(dataset, self.cases, self.teams, {"round": "V1"})
        item = dataset.items[0]
        case = self.cases[item.input["ticketId"]]
        context = contexts[item.input["ticketId"]]
        self.assertEqual(context["expected_answer"], case["expected_answer"])
        self.assertEqual(context["ticket"], case["ticket"])
        self.assertNotIn("expected_answer", context["ticket"])
        self.assertNotIn("ticket", item.metadata)
        self.assertNotIn("teams", item.metadata)
        self.assertTrue(all(isinstance(value, str) and len(value) <= 200 for value in item.metadata.values()))
        self.assertIsNone(original.metadata)
        self.assertIsNone(original.expected_output)
        self.assertEqual(item.id, original.id)
        self.assertEqual(item.dataset_id, original.dataset_id)
        context["ticket"]["description"] = "Changed copy"
        self.assertNotEqual(context["ticket"], case["ticket"])

    def test_task_attaches_full_context_after_small_metadata_has_been_captured(self):
        dataset = self.dataset()
        contexts = prepare_dataset(dataset, self.cases, self.teams, {"round": "V1"})
        item = dataset.items[0]
        captured_metadata = deepcopy(item.metadata)
        case = self.cases[item.input["ticketId"]]
        coordinator = MagicMock(prompt_version="baseline")
        coordinator.analyze.return_value = CoordinationResult.model_validate(case["expected_answer"])
        client = MagicMock()
        with patch("experiments.run.check_database"):
            result = make_task(client, coordinator, MagicMock(), {}, 0, contexts=contexts)(item=item)
        observation = client.update_current_span.call_args.kwargs
        self.assertEqual(observation["metadata"]["ticket"], case["ticket"])
        self.assertEqual(observation["metadata"]["teams"], self.teams)
        self.assertEqual(observation["metadata"]["required_summary_facts"], case["required_summary_facts"])
        self.assertEqual(observation["metadata"]["expected_answer"], case["expected_answer"])
        self.assertEqual(observation["output"], result)
        self.assertEqual(item.metadata["evaluation_ready"], "true")
        self.assertNotIn("teams", captured_metadata)
        self.assertEqual(captured_metadata["evaluation_ready"], "false")

    def test_dataset_accepts_object_and_scalar_id_formats_without_changing_hosted_items(self):
        for encode in (
            lambda ticket_id: {"ticketId": ticket_id},
            lambda ticket_id: json.dumps({"ticketId": ticket_id}),
            lambda ticket_id: ticket_id,
            lambda ticket_id: json.dumps(ticket_id),
            lambda ticket_id: int(ticket_id),
        ):
            dataset = self.dataset()
            dataset.items = [item.model_copy(update={
                "input": encode(json.loads(item.input)["ticketId"]),
            }) for item in dataset.items]
            originals = list(dataset.items)
            inputs = [deepcopy(item.input) for item in originals]
            with self.subTest(sample_input=inputs[0]):
                prepare_dataset(dataset, self.cases, self.teams, {})
                self.assertEqual({item.input["ticketId"] for item in dataset.items}, set(self.cases))
                self.assertTrue(all(set(item.input) == {"ticketId"} for item in dataset.items))
                self.assertEqual([item.input for item in originals], inputs)

    def test_bare_id_with_leading_zeros_is_preserved(self):
        ticket_id = "0" * 23 + "7"
        self.assertEqual(dataset_request(ticket_id, "leading-zero-item").ticketId, ticket_id)

    def test_malformed_dataset_inputs_report_item_and_required_shape(self):
        ticket_id = next(iter(self.cases))
        for value in (
            None, True, float(ticket_id), "{invalid", "E07", [],
            {"ticketId": int(ticket_id)}, {"ticketId": ticket_id, "unexpected": True},
        ):
            with self.subTest(input=value):
                dataset = self.dataset()
                item = dataset.items[0]
                dataset.items[0] = item.model_copy(update={"input": value})
                with self.assertRaisesRegex(ValueError, f"Dataset item {item.id}: Input must be"):
                    prepare_dataset(dataset, self.cases, self.teams, {})

    def test_rounded_numeric_id_is_rejected_instead_of_guessed(self):
        dataset = self.dataset()
        item = dataset.items[0]
        ticket_id = json.loads(item.input)["ticketId"]
        rounded = int(float(ticket_id))
        self.assertNotIn(str(rounded), self.cases)
        dataset.items[0] = item.model_copy(update={"input": rounded})
        with self.assertRaisesRegex(ValueError, f"Dataset item {item.id}: unknown ticket ID"):
            prepare_dataset(dataset, self.cases, self.teams, {})

    def test_duplicate_or_missing_dataset_cases_are_rejected(self):
        dataset = self.dataset()
        dataset.items[-1] = dataset.items[-1].model_copy(update={"input": dataset.items[0].input})
        with self.assertRaises(ValueError):
            prepare_dataset(dataset, self.cases, self.teams, {})

    def test_conflicting_dataset_reference_is_rejected(self):
        dataset = self.dataset()
        item = dataset.items[0]
        ticket_id = json.loads(item.input)["ticketId"]
        expected = deepcopy(self.cases[ticket_id]["expected_answer"])
        expected["summary"] = "A changed reference."
        dataset.items[0] = item.model_copy(update={"expected_output": expected})
        with self.assertRaises(ValueError):
            prepare_dataset(dataset, self.cases, self.teams, {})

    def test_empty_selection_skips_reason_judge_but_keeps_summary_eligible(self):
        case = next(case for case in self.cases.values() if case["case_id"] == "E09")
        item = SimpleNamespace(input={"ticketId": case["ticket"]["_id"]},
                               metadata=build_evaluation_context(case, self.teams, {}))
        coordinator = MagicMock(prompt_version="baseline")
        coordinator.analyze.return_value = CoordinationResult.model_validate(case["expected_answer"])
        client = MagicMock()
        with patch("experiments.run.check_database"):
            result = make_task(client, coordinator, MagicMock(), {}, 0)(item=item)
        self.assertEqual(result["relevantTeams"], [])
        self.assertEqual(item.metadata["evaluation_ready"], "true")
        self.assertEqual(item.metadata["reason_applicable"], "false")

    def test_failed_analysis_is_ineligible_for_both_judges(self):
        case = next(iter(self.cases.values()))
        item = SimpleNamespace(input={"ticketId": case["ticket"]["_id"]},
                               metadata=build_evaluation_context(case, self.teams, {}))
        coordinator = MagicMock(prompt_version="baseline")
        coordinator.analyze.side_effect = RuntimeError("Model unavailable")
        with patch("experiments.run.check_database"):
            result = make_task(MagicMock(), coordinator, MagicMock(), {}, 0)(item=item)
        self.assertIsNone(result)
        self.assertEqual(item.metadata["evaluation_ready"], "false")
        self.assertEqual(item.metadata["reason_applicable"], "false")
        self.assertIn("Model unavailable", item.metadata["execution_error"])

    def test_fixture_failure_is_recorded_without_calling_agent(self):
        case = next(iter(self.cases.values()))
        item = SimpleNamespace(input={"ticketId": case["ticket"]["_id"]},
                               metadata=build_evaluation_context(case, self.teams, {}))
        coordinator = MagicMock(prompt_version="baseline")
        with patch("experiments.run.check_database", side_effect=FixtureMismatchError("Fixture changed")):
            with self.assertRaises(FixtureMismatchError):
                make_task(MagicMock(), coordinator, MagicMock(), {}, 0)(item=item)
        coordinator.analyze.assert_not_called()
        self.assertIn("Fixture changed", item.metadata["infrastructure_error"])
        self.assertNotIn("execution_error", item.metadata)
