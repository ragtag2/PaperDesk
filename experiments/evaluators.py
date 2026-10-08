"""Independent deterministic checks for the final full-agent response.

These functions run in the experiment process. Langfuse's SDK stores their
Evaluation objects on the dataset item's task observation. No model is called.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from langfuse import Evaluation
from pydantic import ValidationError

from agents.schemas import CoordinationResult


SCORE_NAMES = (
    "execution_success",
    "team_exact_match",
    "stakeholder_expected_match",
    "stakeholders_match_selected_teams",
    "application_valid",
)
ID_PATTERN = re.compile(r"^[0-9a-fA-F]{24}$")


def normalized_id(value: Any) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError("Expected a 24-digit hexadecimal ObjectId string.")
    return value.lower()


def team_ids(output: Any) -> list[str]:
    if not isinstance(output, dict) or not isinstance(output.get("relevantTeams"), list):
        raise ValueError("relevantTeams must be an array.")
    result = []
    for team in output["relevantTeams"]:
        if not isinstance(team, dict):
            raise ValueError("Each relevant team must be an object.")
        result.append(normalized_id(team.get("teamId")))
    return result


def stakeholder_ids(output: Any) -> list[str]:
    if not isinstance(output, dict) or not isinstance(output.get("stakeholderUserIds"), list):
        raise ValueError("stakeholderUserIds must be an array.")
    return [normalized_id(value) for value in output["stakeholderUserIds"]]


def active_members(selected: set[str], users: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        normalized_id(str(user["_id"]))
        for user in users
        if user["isActive"] is True and user.get("teamId") is not None
        and normalized_id(str(user["teamId"])) in selected
    }


def score(name: str, passed: bool, comment: str, **details: Any) -> Evaluation:
    return Evaluation(name=name, value=int(passed), comment=comment,
                      metadata=details or None, data_type="NUMERIC")


def set_score(name: str, actual: set[str], expected: set[str]) -> Evaluation:
    missing, extra = sorted(expected - actual), sorted(actual - expected)
    return score(name, actual == expected,
                 "Sets match." if actual == expected else f"Missing: {missing}; extra: {extra}.",
                 missing=missing, extra=extra)


def reference_answer(expected_output: Any) -> dict[str, Any]:
    # Invalid reference data is an evaluator error, never an agent-quality zero.
    return CoordinationResult.model_validate(expected_output, strict=True).model_dump(mode="json")


def execution_success(*, output: Any, metadata: dict | None = None, **_kwargs) -> Evaluation:
    passed = output is not None
    comment = "The analysis returned a result." if passed else (
        (metadata or {}).get("execution_error") or "The analysis did not return a result."
    )
    return score("execution_success", passed, comment)


def team_exact_match(*, output: Any, expected_output: Any, **_kwargs) -> Evaluation:
    expected = set(team_ids(reference_answer(expected_output)))
    try:
        actual = set(team_ids(output))
    except ValueError as error:
        return score("team_exact_match", False, str(error))
    return set_score("team_exact_match", actual, expected)


def stakeholder_expected_match(*, output: Any, expected_output: Any, **_kwargs) -> Evaluation:
    expected = set(stakeholder_ids(reference_answer(expected_output)))
    try:
        actual = set(stakeholder_ids(output))
    except ValueError as error:
        return score("stakeholder_expected_match", False, str(error))
    return set_score("stakeholder_expected_match", actual, expected)


def stakeholders_match_selected_teams(*, output: Any, teams: Sequence[Mapping[str, Any]],
                                     users: Sequence[Mapping[str, Any]], **_kwargs) -> Evaluation:
    known = {normalized_id(str(team["_id"])) for team in teams}
    try:
        selected, actual = set(team_ids(output)), set(stakeholder_ids(output))
    except ValueError as error:
        return score("stakeholders_match_selected_teams", False, str(error))
    if not selected <= known:
        return score("stakeholders_match_selected_teams", False, "Selected teams include unknown IDs.")
    return set_score("stakeholders_match_selected_teams", actual, active_members(selected, users))


def application_valid(*, input: dict, output: Any, teams: Sequence[Mapping[str, Any]],
                      users: Sequence[Mapping[str, Any]], **_kwargs) -> Evaluation:
    ticket_id = normalized_id(input["ticketId"])
    known_teams = {normalized_id(str(team["_id"])) for team in teams}
    known_users = {normalized_id(str(user["_id"])) for user in users}
    try:
        parsed = CoordinationResult.model_validate(output, strict=True).model_dump(mode="json")
    except ValidationError:
        return score("application_valid", False, "The response does not satisfy CoordinationResult.")
    selected, members = team_ids(parsed), stakeholder_ids(parsed)
    checks = {
        "ticket_id_matches": normalized_id(parsed["ticketId"]) == ticket_id,
        "known_teams": set(selected) <= known_teams,
        "known_users": set(members) <= known_users,
        "unique_teams": len(selected) == len(set(selected)),
        "unique_stakeholders": len(members) == len(set(members)),
        "active_membership_matches": set(members) == active_members(set(selected), users),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return score("application_valid", not failures,
                 "All application constraints pass." if not failures else f"Failed: {', '.join(failures)}.",
                 checks=checks)


def evaluate_result(*, input: dict, output: Any, expected_output: Any,
                    teams: Sequence[Mapping[str, Any]], users: Sequence[Mapping[str, Any]],
                    metadata: dict | None = None, **_kwargs) -> list[Evaluation]:
    values = dict(input=input, output=output, expected_output=expected_output,
                  teams=teams, users=users, metadata=metadata)
    return [function(**values) for function in (
        execution_success, team_exact_match, stakeholder_expected_match,
        stakeholders_match_selected_teams, application_valid,
    )]
