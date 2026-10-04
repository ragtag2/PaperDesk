"""Exercise the real LangChain tool loop without a live model or MongoDB."""

import json
import unittest
from unittest.mock import MagicMock

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agents.agent import IncidentCoordinator
from agents.database import MongoDatabase


TICKET_ID = "507f1f77bcf86cd799439011"
IT_ID = "507f1f77bcf86cd799439012"
FINANCE_ID = "507f1f77bcf86cd799439013"
IT_USER_ID = "507f1f77bcf86cd799439014"
FINANCE_USER_ID = "507f1f77bcf86cd799439015"


class ScriptedChatModel(BaseChatModel):
    responses: list[AIMessage]
    position: int = 0
    observed_messages: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "scripted-test-model"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.observed_messages.append(list(messages))
        message = self.responses[self.position]
        self.position += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def scripted_responses(selected_teams):
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_ticket",
                    "args": {"ticket_id": TICKET_ID},
                    "id": "read-ticket",
                    "type": "tool_call",
                },
                {
                    "name": "list_teams",
                    "args": {},
                    "id": "read-teams",
                    "type": "tool_call",
                },
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "TeamAssessment",
                    "args": {
                        "summary": "The payroll application is unavailable.",
                        "relevantTeams": [
                            {"teamId": team_id, "reason": reason}
                            for team_id, reason in selected_teams
                        ],
                    },
                    "id": "team-assessment",
                    "type": "tool_call",
                }
            ],
        ),
    ]


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.database = MagicMock(spec=MongoDatabase)
        self.database.get_ticket.return_value = {
            "_id": TICKET_ID,
            "title": "Payroll unavailable",
            "description": "Finance cannot approve salaries.",
        }
        self.database.list_teams.return_value = [
            {"_id": IT_ID, "name": "IT", "responsibilities": "Maintains applications."},
            {
                "_id": FINANCE_ID,
                "name": "Finance",
                "responsibilities": "Processes payroll.",
            },
        ]
        self.database.get_team_members.side_effect = lambda team_id: [
            {"_id": IT_USER_ID if team_id == IT_ID else FINANCE_USER_ID}
        ]

    def test_tool_loop_reads_context_and_assembles_all_team_members(self):
        model = ScriptedChatModel(
            responses=scripted_responses(
                [(IT_ID, "Maintains the application."), (FINANCE_ID, "Payroll is blocked.")]
            )
        )
        coordinator = IncidentCoordinator(self.database, model)

        result = coordinator.analyze(TICKET_ID)

        self.assertEqual(result.ticketId, TICKET_ID)
        self.assertEqual([team.teamId for team in result.relevantTeams], [IT_ID, FINANCE_ID])
        self.assertEqual(result.stakeholderUserIds, [IT_USER_ID, FINANCE_USER_ID])
        observations = {
            message.name: json.loads(message.content)
            for message in model.observed_messages[1]
            if isinstance(message, ToolMessage)
        }
        self.assertEqual(observations["get_ticket"], self.database.get_ticket.return_value)
        self.assertEqual(observations["list_teams"], self.database.list_teams.return_value)

    def test_second_analysis_uses_new_ticket_data_and_replaces_stakeholders(self):
        model = ScriptedChatModel(
            responses=(
                scripted_responses([(IT_ID, "Investigates the application.")])
                + scripted_responses([(FINANCE_ID, "Only payroll approvals remain blocked.")])
            )
        )
        coordinator = IncidentCoordinator(self.database, model)
        first = coordinator.analyze(TICKET_ID)
        self.database.get_ticket.return_value = {
            "_id": TICKET_ID,
            "description": "The application is restored; Finance needs to retry approval.",
            "coordination": first.model_dump(),
        }

        second = coordinator.analyze(TICKET_ID)

        self.assertEqual(first.stakeholderUserIds, [IT_USER_ID])
        self.assertEqual(second.stakeholderUserIds, [FINANCE_USER_ID])
        observations = {
            message.name: json.loads(message.content)
            for message in model.observed_messages[-1]
            if isinstance(message, ToolMessage)
        }
        self.assertIn("restored", observations["get_ticket"]["description"])

    def test_no_relevant_teams_returns_no_stakeholders(self):
        model = ScriptedChatModel(responses=scripted_responses([]))

        result = IncidentCoordinator(self.database, model).analyze(TICKET_ID)

        self.assertEqual(result.relevantTeams, [])
        self.assertEqual(result.stakeholderUserIds, [])
        self.database.get_team_members.assert_not_called()
