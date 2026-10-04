import assert from 'node:assert/strict'
import { test } from 'node:test'
import { Types } from 'mongoose'
import type { TicketRecord } from '../src/modules/tickets/ticket.model.js'

process.env.MONGODB_URI = 'mongodb://127.0.0.1:27018'
process.env.SESSION_SECRET = 'ticket-display-test-secret-with-at-least-32-characters'

const { TicketModel } = await import('../src/modules/tickets/ticket.model.js')
const { UserModel } = await import('../src/modules/users/user.model.js')
const { TeamModel } = await import('../src/modules/teams/team.model.js')
const { getTicket, listTickets } = await import('../src/modules/tickets/tickets.service.js')

const creatorId = new Types.ObjectId()
const stakeholderId = new Types.ObjectId()
const teamId = new Types.ObjectId()
const ticket: TicketRecord = {
  _id: new Types.ObjectId(), title: 'Payroll unavailable', description: 'The payroll application cannot be opened.',
  category: 'software', priority: 'medium', status: 'open', creatorId, assigneeId: null,
  createdAt: new Date('2026-10-02T08:00:00Z'), updatedAt: new Date('2026-10-02T08:00:00Z'),
  coordination: {
    summary: 'Payroll access is interrupted.', relevantTeams: [{ teamId, reason: 'IT maintains application access.' }],
    stakeholderUserIds: [stakeholderId], analyzedAt: new Date('2026-10-02T08:01:00Z'),
  },
}
const actor = { userId: String(creatorId), role: 'employee' as const }

test('employee ticket detail resolves coordination names and filters by owner or stakeholder', async (t) => {
  const find = t.mock.method(TicketModel, 'findOne', () => ({ lean: async () => ticket }))
  const users = t.mock.method(UserModel, 'find', () => ({ select: (fields: string) => {
    assert.equal(fields, 'name')
    return { lean: async () => [{ _id: creatorId, name: 'Ticket owner' }, { _id: stakeholderId, name: 'Mia Chen' }] }
  } }))
  const teams = t.mock.method(TeamModel, 'find', () => ({ select: (fields: string) => {
    assert.equal(fields, 'name')
    return { lean: async () => [{ _id: teamId, name: 'IT' }] }
  } }))

  const result = await getTicket(String(ticket._id), actor)

  assert.deepEqual(find.mock.calls[0]!.arguments[0], {
    _id: ticket._id,
    $or: [{ creatorId: actor.userId }, { 'coordination.stakeholderUserIds': actor.userId }],
  })
  assert.deepEqual(users.mock.calls[0]!.arguments[0], { _id: { $in: [String(creatorId), String(stakeholderId)] } })
  assert.deepEqual(teams.mock.calls[0]!.arguments[0], { _id: { $in: [String(teamId)] } })
  assert.deepEqual(result!.coordination?.relevantTeams, [{ teamId: String(teamId), name: 'IT', reason: 'IT maintains application access.' }])
  assert.deepEqual(result!.coordination?.stakeholders, [{ _id: String(stakeholderId), name: 'Mia Chen' }])
  assert.deepEqual(result!.coordination?.stakeholderUserIds, [String(stakeholderId)])
  assert.equal(result!.coordination?.analyzedAt, '2026-10-02T08:01:00.000Z')
})

test('ticket lists resolve current directory names without changing saved analysis', async (t) => {
  t.mock.method(TicketModel, 'find', () => ({ sort: () => ({ skip: () => ({ limit: () => ({ lean: async () => [ticket] }) }) }) }))
  t.mock.method(TicketModel, 'countDocuments', async () => 1)
  t.mock.method(UserModel, 'find', () => ({ select: () => ({ lean: async () => [{ _id: creatorId, name: 'Owner' }, { _id: stakeholderId, name: 'Mia Updated' }] }) }))
  t.mock.method(TeamModel, 'find', () => ({ select: () => ({ lean: async () => [{ _id: teamId, name: 'IT Operations' }] }) }))

  const result = await listTickets(actor, { page: 1, limit: 10 })

  assert.equal(result.items[0]!.coordination?.relevantTeams[0]!.name, 'IT Operations')
  assert.equal(result.items[0]!.coordination?.stakeholders[0]!.name, 'Mia Updated')
  assert.equal(result.items[0]!.coordination?.summary, ticket.coordination!.summary)
  assert.equal(result.total, 1)
})

test('tickets without analysis return null without querying teams', async (t) => {
  t.mock.method(TicketModel, 'findOne', () => ({ lean: async () => ({ ...ticket, coordination: null }) }))
  t.mock.method(UserModel, 'find', () => ({ select: () => ({ lean: async () => [{ _id: creatorId, name: 'Owner' }] }) }))
  const teams = t.mock.method(TeamModel, 'find', () => { throw new Error('Unexpected team query') })

  assert.equal((await getTicket(String(ticket._id), actor))!.coordination, null)
  assert.equal(teams.mock.callCount(), 0)
})
