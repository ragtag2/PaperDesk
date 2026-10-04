import { Types } from 'mongoose'
import { UserModel } from '../users/user.model.js'
import { TeamModel } from '../teams/team.model.js'
import { HttpError } from '../../shared/httpError.js'
import { objectId } from '../../shared/objectId.js'
import { pageResult } from '../../shared/pagination.js'
import { serializeTicket } from '../../shared/serialize.js'
import { TicketModel, type TicketRecord } from './ticket.model.js'
import { assertCanDelete, assertCanPatch, isStaff, visibleFilter, type Actor } from './ticketPermissions.js'
import type { CreateTicketInput, TicketsQuery, UpdateTicketInput } from './tickets.schemas.js'
import { scheduleTicketCoordination } from './ticketCoordination.js'
import { notifyTicketResolved } from '../notifications/notifications.service.js'

async function enrich(tickets: TicketRecord[]) {
  const ids = [...new Set(tickets.flatMap((ticket) => [
    String(ticket.creatorId),
    ...(ticket.assigneeId ? [String(ticket.assigneeId)] : []),
    ...(ticket.coordination?.stakeholderUserIds.map(String) ?? []),
  ]))]
  const teamIds = [...new Set(tickets.flatMap((ticket) => ticket.coordination?.relevantTeams.map((team) => String(team.teamId)) ?? []))]
  const [users, teams] = await Promise.all([
    UserModel.find({ _id: { $in: ids } }).select('name').lean(),
    teamIds.length ? TeamModel.find({ _id: { $in: teamIds } }).select('name').lean() : [],
  ])
  const people = new Map(users.map((user) => [String(user._id), user]))
  const teamNames = new Map(teams.map((team) => [String(team._id), team.name]))
  return tickets.map((ticket) => serializeTicket(ticket, people, teamNames))
}

async function findVisible(id: string, actor: Actor) {
  const ticket = await TicketModel.findOne({ _id: objectId(id), ...visibleFilter(actor) }).lean()
  if (!ticket) throw new HttpError(404, 'Ticket not found.')
  return ticket
}

export async function listTickets(actor: Actor, query: TicketsQuery) {
  if (query.assigneeId && !isStaff(actor)) throw new HttpError(403, 'Forbidden.')
  const filter = {
    ...visibleFilter(actor),
    ...(query.status ? { status: query.status } : {}),
    ...(query.priority ? { priority: query.priority } : {}),
    ...(query.category ? { category: query.category } : {}),
    ...(query.assigneeId ? { assigneeId: objectId(query.assigneeId) } : {}),
    ...(query.involvingMe ? { 'coordination.stakeholderUserIds': objectId(actor.userId) } : {}),
  }
  const [tickets, total] = await Promise.all([
    TicketModel.find(filter).sort({ createdAt: -1, _id: -1 }).skip((query.page - 1) * query.limit).limit(query.limit).lean(),
    TicketModel.countDocuments(filter),
  ])
  return pageResult(await enrich(tickets), query.page, query.limit, total)
}

export async function createTicket(actor: Actor, input: CreateTicketInput) {
  const ticket = await TicketModel.create({ ...input, creatorId: objectId(actor.userId) })
  const result = (await enrich([ticket]))[0]
  scheduleTicketCoordination(ticket)
  return result
}

export async function getTicket(id: string, actor: Actor) {
  return (await enrich([await findVisible(id, actor)]))[0]
}

export async function updateTicket(id: string, actor: Actor, patch: UpdateTicketInput) {
  const ticket = await findVisible(id, actor)
  assertCanPatch(actor, ticket, patch)
  if (patch.assigneeId) {
    const assignee = await UserModel.findOne({ _id: objectId(patch.assigneeId), isActive: true, role: { $in: ['support', 'admin'] } }).select('_id').lean()
    if (!assignee) throw new HttpError(400, 'Assignee must be an active support or admin user.')
  }
  const updated = await TicketModel.findByIdAndUpdate(ticket._id, {
    ...patch,
    ...(patch.assigneeId ? { assigneeId: new Types.ObjectId(patch.assigneeId) } : {}),
  }, { returnDocument: 'after', runValidators: true }).lean()
  if (!updated) throw new HttpError(404, 'Ticket not found.')
  const result = (await enrich([updated]))[0]
  try { await notifyTicketResolved(ticket, updated) }
  catch { console.warn(`Resolution notifications failed for saved ticket ${id}.`) }
  scheduleTicketCoordination(updated)
  return result
}

export async function deleteTicket(id: string, actor: Actor) {
  const ticket = await findVisible(id, actor)
  assertCanDelete(actor, ticket)
  await TicketModel.deleteOne({ _id: ticket._id })
}

export async function listAssignees() {
  const users = await UserModel.find({ isActive: true, role: { $in: ['support', 'admin'] } }).select('_id name').sort({ name: 1, _id: 1 }).lean()
  return users.map((user) => ({ _id: String(user._id), name: user.name }))
}
