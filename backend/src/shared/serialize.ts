import type { TicketRecord } from '../modules/tickets/ticket.model.js'
import type { UserRecord } from '../modules/users/user.model.js'
import type { TeamRecord } from '../modules/teams/team.model.js'

export function serializeTeam(team: TeamRecord) {
  return {
    _id: String(team._id),
    name: team.name,
    responsibilities: team.responsibilities,
    createdAt: team.createdAt.toISOString(),
    updatedAt: team.updatedAt.toISOString(),
  }
}

export function serializeUser(user: UserRecord) {
  return {
    _id: String(user._id),
    name: user.name,
    email: user.email,
    role: user.role,
    isActive: user.isActive,
    teamId: user.teamId ? String(user.teamId) : null,
    createdAt: user.createdAt.toISOString(),
    updatedAt: user.updatedAt.toISOString(),
  }
}

export function serializeTicket(ticket: TicketRecord, people: Map<string, Pick<UserRecord, '_id' | 'name'>>, teamNames: Map<string, string>) {
  const creator = people.get(String(ticket.creatorId))
  if (!creator) throw new Error('Ticket creator is missing.')
  const assignee = ticket.assigneeId ? people.get(String(ticket.assigneeId)) : undefined
  return {
    _id: String(ticket._id),
    title: ticket.title,
    description: ticket.description,
    category: ticket.category,
    priority: ticket.priority,
    status: ticket.status,
    creatorId: String(ticket.creatorId),
    assigneeId: ticket.assigneeId ? String(ticket.assigneeId) : null,
    creator: { _id: String(creator._id), name: creator.name },
    assignee: assignee ? { _id: String(assignee._id), name: assignee.name } : null,
    coordination: ticket.coordination ? {
      summary: ticket.coordination.summary,
      relevantTeams: ticket.coordination.relevantTeams.map((team) => ({
        teamId: String(team.teamId), name: teamNames.get(String(team.teamId)) ?? null, reason: team.reason,
      })),
      stakeholderUserIds: ticket.coordination.stakeholderUserIds.map(String),
      stakeholders: ticket.coordination.stakeholderUserIds.flatMap((id) => {
        const person = people.get(String(id))
        return person ? [{ _id: String(person._id), name: person.name }] : []
      }),
      analyzedAt: ticket.coordination.analyzedAt.toISOString(),
    } : null,
    createdAt: ticket.createdAt.toISOString(),
    updatedAt: ticket.updatedAt.toISOString(),
  }
}
