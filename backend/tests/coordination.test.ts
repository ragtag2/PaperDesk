import assert from 'node:assert/strict'
import { test } from 'node:test'
import { Types } from 'mongoose'
import type { TicketRecord } from '../src/modules/tickets/ticket.model.js'

process.env.MONGODB_URI = 'mongodb://127.0.0.1:27018'
process.env.SESSION_SECRET = 'coordination-test-secret-with-at-least-32-characters'
process.env.AGENT_BASE_URL = 'http://agent.test/'

const { analyzeTicket } = await import('../src/integrations/agent.client.js')
const { coordinateTicket, scheduleTicketCoordination } = await import('../src/modules/tickets/ticketCoordination.js')
const { TicketModel } = await import('../src/modules/tickets/ticket.model.js')
const { env } = await import('../src/config/env.js')

const ticketId = '507f1f77bcf86cd799439011'
const teamId = '507f1f77bcf86cd799439012'
const userId = '507f1f77bcf86cd799439013'
const result = {
  ticketId,
  summary: 'Payroll is unavailable.',
  relevantTeams: [{ teamId, reason: 'IT maintains the application.' }],
  stakeholderUserIds: [userId],
}
const previousTicket: TicketRecord = {
  _id: new Types.ObjectId(ticketId), title: 'Payroll unavailable', description: 'Payroll access is interrupted.',
  category: 'software', priority: 'medium', status: 'open', creatorId: new Types.ObjectId(userId), assigneeId: null,
  createdAt: new Date('2026-10-02T08:00:00.000Z'), updatedAt: new Date('2026-10-02T08:00:00.000Z'),
  coordination: {
    summary: 'Previous payroll analysis.', relevantTeams: [{ teamId: new Types.ObjectId(teamId), reason: 'IT maintains payroll.' }],
    stakeholderUserIds: [new Types.ObjectId(userId)], analyzedAt: new Date('2026-10-02T08:01:00.000Z'),
  },
}

test('agent client sends only the ticket ID and validates the result', async (t) => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(result)))

  assert.deepEqual(await analyzeTicket(ticketId), result)

  const [url, options] = fetchMock.mock.calls[0]!.arguments as unknown as [string, RequestInit]
  assert.equal(url, 'http://agent.test/analyze-ticket')
  assert.equal(options.method, 'POST')
  assert.deepEqual(JSON.parse(options.body as string), { ticketId })
  assert.ok(options.signal instanceof AbortSignal)
})

test('agent client rejects failed, malformed, and mismatched responses', async (t) => {
  let response = new Response('{}', { status: 502 })
  t.mock.method(globalThis, 'fetch', async () => response)
  await assert.rejects(analyzeTicket(ticketId), /HTTP 502/)

  response = new Response(JSON.stringify({ ...result, stakeholderUserIds: ['invalid'] }))
  await assert.rejects(analyzeTicket(ticketId))

  response = new Response(JSON.stringify({ ...result, ticketId: teamId }))
  await assert.rejects(analyzeTicket(ticketId), /different ticket ID/)
})

test('coordination saves MongoDB references only for the analyzed ticket version', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(result)))
  const save = t.mock.method(TicketModel, 'findOneAndUpdate', () => ({ lean: async () => previousTicket }))
  const updatedAt = previousTicket.updatedAt

  assert.deepEqual(await coordinateTicket(ticketId, updatedAt), { result, saved: true })

  const [filter, update, options] = save.mock.calls[0]!.arguments as unknown as [
    { _id: Types.ObjectId; updatedAt: Date },
    { $set: { coordination: { summary: string; relevantTeams: { teamId: Types.ObjectId }[]; stakeholderUserIds: Types.ObjectId[]; analyzedAt: Date } } },
    { timestamps: boolean; runValidators: boolean; returnDocument: string },
  ]
  assert.equal(String(filter._id), ticketId)
  assert.equal(filter.updatedAt, updatedAt)
  assert.equal(update.$set.coordination.summary, result.summary)
  assert.equal(String(update.$set.coordination.relevantTeams[0]!.teamId), teamId)
  assert.equal(String(update.$set.coordination.stakeholderUserIds[0]), userId)
  assert.ok(update.$set.coordination.analyzedAt instanceof Date)
  assert.deepEqual(options, { runValidators: true, timestamps: false, returnDocument: 'before' })
})

test('background scheduling returns before the agent finishes', async (t) => {
  let finish!: (response: Response) => void
  const pending = new Promise<Response>((resolve) => { finish = resolve })
  t.mock.method(globalThis, 'fetch', () => pending)
  let saved!: () => void
  const completed = new Promise<void>((resolve) => { saved = resolve })
  const save = t.mock.method(TicketModel, 'findOneAndUpdate', () => ({ lean: async () => { saved(); return previousTicket } }))

  assert.equal(scheduleTicketCoordination({ _id: new Types.ObjectId(ticketId), updatedAt: new Date() }), undefined)
  assert.equal(save.mock.callCount(), 0)
  finish(new Response(JSON.stringify(result)))
  await completed
  assert.equal(save.mock.callCount(), 1)
})

test('analysis is skipped when the agent URL is not configured', (t) => {
  const originalUrl = env.AGENT_BASE_URL
  env.AGENT_BASE_URL = undefined
  t.after(() => { env.AGENT_BASE_URL = originalUrl })
  const fetchMock = t.mock.method(globalThis, 'fetch', () => { throw new Error('Unexpected request.') })

  scheduleTicketCoordination({ _id: new Types.ObjectId(ticketId), updatedAt: new Date() })

  assert.equal(fetchMock.mock.callCount(), 0)
})
