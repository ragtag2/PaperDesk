"""The public agent API and the model's team selection format."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


ObjectIdString = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-fA-F]{24}$")
]
NonEmptyString = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class AnalyzeTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticketId: ObjectIdString


class ErrorResponse(BaseModel):
    message: str


class RelevantTeam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teamId: ObjectIdString = Field(description="The team's MongoDB ObjectId.")
    reason: NonEmptyString = Field(
        description="Why this team is responsible for or affected by this ticket."
    )


class TeamAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: NonEmptyString
    relevantTeams: list[RelevantTeam]


class CoordinationResult(TeamAssessment):
    ticketId: ObjectIdString
    stakeholderUserIds: list[ObjectIdString]
