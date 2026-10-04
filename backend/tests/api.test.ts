import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import bcrypt from 'bcryptjs'
import mongoose from 'mongoose'
import request from 'supertest'
import type { Express } from 'express'

process.env.MONGODB_URI = 'mongodb://127.0.0.1:27018'
process.env.MONGODB_DB_NAME = `paperdesk_test_${Date.now()}`
process.env.SESSION_SECRET = 'local-test-secret-with-at-least-32-characters'
process.env.FRONTEND_ORIGIN = 'http://localhost:5173'
process.env.NODE_ENV = 'test'
process.env.AGENT_BASE_URL = ''

let app: Express
let UserModel: typeof import('../src/modules/users/user.model.js').UserModel
let TicketModel: typeof import('../src/modules/tickets/ticket.model.js').TicketModel
let TeamModel: typeof import('../src/modules/teams/team.model.js').TeamModel

before(async () => {
  const [{ createApp }, users, tickets, teams] = await Promise.all([
    import('../src/app.js'), import('../src/modules/users/user.model.js'), import('../src/modules/tickets/ticket.model.js'),
    import('../src/modules/teams/team.model.js'),
  ])
  UserModel = users.UserModel
  TicketModel = tickets.TicketModel
  TeamModel = teams.TeamModel
  await mongoose.connect(process.env.MONGODB_URI!, { dbName: process.env.MONGODB_DB_NAME })
  await UserModel.init()
  app = createApp()
})

after(async () => {
  if (mongoose.connection.readyState === 1) await mongoose.connection.dropDatabase()
  await mongoose.disconnect()
})

async function employeeSession(email: string) {
  const agent = request.agent(app)
  const signup = await agent.post('/auth/signup').send({ name: 'Alice', email, password: 'password123' })
  assert.equal(signup.status, 201)
  assert.equal((await agent.post('/auth/login').send({ email, password: 'password123' })).status, 204)
  return { agent, userId: signup.body._id as string }
}

async function createTicket(agent: ReturnType<typeof request.agent>, title: string, category: string) {
  const response = await agent.post('/tickets').send({ title, description: 'Test description', category })
  assert.equal(response.status, 201)
  return response.body._id as string
}

test('cookie auth, ticket permissions, users, validation, and revocation', async () => {
  const employee = request.agent(app)
  const otherEmployee = request.agent(app)
  const admin = request.agent(app)
  const support = request.agent(app)

  const signup = await employee.post('/auth/signup').send({ name: '  Alice  ', email: ' ALICE@example.com ', password: 'password123' })
  assert.equal(signup.status, 201)
  assert.equal(signup.body.name, 'Alice')
  assert.equal(signup.body.email, 'alice@example.com')
  assert.equal(signup.body.role, 'employee')
  assert.match(signup.body._id, /^[a-f\d]{24}$/)
  assert.ok(signup.body.createdAt)
  assert.ok(signup.body.updatedAt)
  assert.equal('passwordHash' in signup.body, false)
  assert.equal((await employee.post('/auth/signup').send({ name: 'Alice', email: 'alice@example.com', password: 'password123' })).status, 409)
  assert.equal((await employee.get('/users/me')).status, 401)
  const login = await employee.post('/auth/login').send({ email: 'alice@example.com', password: 'password123' })
  assert.equal(login.status, 204)
  assert.match(login.headers['set-cookie']?.[0] ?? '', /^paperdesk\.sid=/)
  assert.match(login.headers['set-cookie']?.[0] ?? '', /HttpOnly/)
  assert.match(login.headers['set-cookie']?.[0] ?? '', /SameSite=Lax/)
  assert.equal((await employee.get('/users/me')).status, 200)

  assert.equal((await otherEmployee.post('/auth/signup').send({ name: 'Bob', email: 'bob@example.com', password: 'password123' })).status, 201)
  assert.equal((await otherEmployee.post('/auth/login').send({ email: 'bob@example.com', password: 'password123' })).status, 204)

  const ticket = await employee.post('/tickets').send({ title: '  Broken laptop  ', description: '  Screen is blank  ', category: 'hardware' })
  assert.equal(ticket.status, 201)
  assert.equal(ticket.body.title, 'Broken laptop')
  assert.equal(ticket.body.status, 'open')
  assert.equal(ticket.body.priority, 'medium')
  assert.equal(ticket.body.assignee, null)
  assert.deepEqual(ticket.body.creator, { _id: signup.body._id, name: 'Alice' })
  const ticketId: string = ticket.body._id
  assert.equal((await otherEmployee.get(`/tickets/${ticketId}`)).status, 404)
  assert.equal((await otherEmployee.patch(`/tickets/${ticketId}`).send({ title: 'No' })).status, 404)
  assert.equal((await employee.patch(`/tickets/${ticketId}`).send({ priority: 'high' })).status, 403)
  assert.equal((await employee.patch(`/tickets/${ticketId}`).send({ title: 'Yes', priority: 'high' })).status, 403)
  assert.equal((await employee.patch(`/tickets/${ticketId}`).send({ unexpected: true })).status, 400)
  assert.equal((await employee.get('/tickets?limit=101')).status, 400)
  assert.equal((await employee.get('/tickets?unknown=true')).status, 400)
  assert.equal((await employee.get('/tickets?assigneeId=000000000000000000000001')).status, 403)
  const employeeList = await employee.get('/tickets?page=2&limit=1')
  assert.equal(employeeList.status, 200)
  assert.deepEqual(employeeList.body, { items: [], page: 2, limit: 1, total: 1 })

  await UserModel.create({ name: 'Admin', email: 'admin@example.com', passwordHash: await bcrypt.hash('password123', 12), role: 'admin' })
  assert.equal((await admin.post('/auth/login').send({ email: 'admin@example.com', password: 'password123' })).status, 204)
  const staff = await admin.post('/users').send({ name: 'Sam', email: 'sam@example.com', password: 'password123', role: 'support' })
  assert.equal(staff.status, 201)
  assert.equal((await admin.get(`/users/${staff.body._id}`)).status, 200)
  assert.equal((await support.post('/auth/login').send({ email: 'sam@example.com', password: 'password123' })).status, 204)
  const assignees = await support.get('/tickets/assignees')
  assert.equal(assignees.status, 200)
  assert.ok(assignees.body.some((item: { _id: string }) => item._id === staff.body._id))
  const triaged = await support.patch(`/tickets/${ticketId}`).send({ status: 'in_progress', assigneeId: staff.body._id })
  assert.equal(triaged.status, 200)
  assert.deepEqual(triaged.body.assignee, { _id: staff.body._id, name: 'Sam' })
  assert.equal((await support.get('/tickets')).body.total, 1)
  assert.equal((await employee.patch(`/tickets/${ticketId}`).send({ title: 'Too late' })).status, 403)
  assert.equal((await employee.delete(`/tickets/${ticketId}`)).status, 403)
  assert.equal((await support.patch(`/tickets/${ticketId}`).send({ title: 'Not mine' })).status, 403)
  assert.equal((await admin.patch(`/tickets/${ticketId}`).send({ title: 'Admin edit' })).status, 200)

  assert.equal((await admin.patch(`/users/${staff.body._id}`).send({ isActive: false })).status, 200)
  assert.equal((await admin.get('/users?isActive=false')).body.total, 1)
  assert.equal((await admin.patch(`/tickets/${ticketId}`).send({ assigneeId: staff.body._id })).status, 400)
  assert.equal((await support.get('/users/me')).status, 401)
  assert.equal((await support.post('/auth/login').send({ email: 'sam@example.com', password: 'password123' })).status, 401)
  assert.equal((await admin.patch(`/users/${staff.body._id}`).send({ isActive: true })).status, 200)
  assert.equal((await support.get('/users/me')).status, 401)
  assert.equal((await support.post('/auth/login').send({ email: 'sam@example.com', password: 'password123' })).status, 204)
  assert.equal((await admin.delete(`/users/${staff.body._id}`)).status, 204)
  assert.equal((await admin.delete(`/users/${staff.body._id}`)).status, 204)
  assert.equal((await support.get('/users/me')).status, 401)
  assert.equal((await admin.patch(`/users/${signup.body._id}`).send({ role: 'admin' })).status, 200)
  assert.equal((await admin.patch('/users/not-an-id').send({ name: 'x' })).status, 400)
  const adminId: string = (await admin.get('/users/me')).body._id
  assert.equal((await admin.patch(`/users/${adminId.toUpperCase()}`).send({ role: 'employee' })).status, 403)
  assert.equal((await admin.delete(`/users/${adminId.toUpperCase()}`)).status, 403)

  assert.equal((await employee.patch('/users/me/password').send({ currentPassword: 'wrong', newPassword: 'newpassword123' })).status, 400)
  assert.equal((await employee.patch('/users/me/password').send({ currentPassword: 'password123', newPassword: 'newpassword123' })).status, 204)
  assert.equal((await employee.get('/users/me')).status, 200)
  assert.equal((await employee.post('/auth/logout')).status, 204)
  assert.equal((await employee.get('/users/me')).status, 401)
  assert.equal((await admin.delete(`/tickets/${ticketId}`)).status, 204)
  assert.equal((await admin.get(`/tickets/${ticketId}`)).status, 404)

  const badOrigin = await request(app).post('/auth/signup').set('Origin', 'https://evil.example').send({ name: 'X', email: 'x@example.com', password: 'password123' })
  assert.equal(badOrigin.status, 403)
  assert.deepEqual(Object.keys(badOrigin.body), ['message'])
  const preflight = await request(app).options('/tickets').set('Origin', 'http://localhost:5173').set('Access-Control-Request-Method', 'POST').set('Access-Control-Request-Headers', 'Content-Type')
  assert.equal(preflight.status, 204)
  assert.equal(preflight.headers['access-control-allow-origin'], 'http://localhost:5173')
  assert.equal(preflight.headers['access-control-allow-credentials'], 'true')
  assert.match(preflight.headers.vary ?? '', /Origin/)
})

test('PATCH /users/me saves normalized profile fields', async () => {
  const { agent, userId } = await employeeSession('profile@example.com')
  const updated = await agent.patch('/users/me').send({ name: '  New Name  ', email: 'NEW@example.com' })
  assert.equal(updated.status, 200)
  assert.equal(updated.body._id, userId)
  assert.equal(updated.body.name, 'New Name')
  assert.equal(updated.body.email, 'new@example.com')

  const profile = await agent.get('/users/me')
  assert.equal(profile.status, 200)
  assert.equal(profile.body.name, 'New Name')
  assert.equal(profile.body.email, 'new@example.com')
})

test('GET /tickets/:id lets the owner read a ticket', async () => {
  const { agent, userId } = await employeeSession('ticket-reader@example.com')
  const ticketId = await createTicket(agent, 'Own ticket', 'hardware')
  const response = await agent.get(`/tickets/${ticketId}`)
  assert.equal(response.status, 200)
  assert.equal(response.body._id, ticketId)
  assert.equal(response.body.creatorId, userId)
  assert.deepEqual(response.body.creator, { _id: userId, name: 'Alice' })
})

test('POST /auth/login rejects a wrong password without creating a session', async () => {
  await employeeSession('wrong-password@example.com')
  const visitor = request.agent(app)
  const response = await visitor.post('/auth/login').send({ email: 'wrong-password@example.com', password: 'incorrect' })
  assert.equal(response.status, 401)
  assert.equal((await visitor.get('/users/me')).status, 401)
})

test('GET /tickets filters by category, priority, and status', async () => {
  const { agent } = await employeeSession('ticket-filters@example.com')
  const hardwareOpen = await createTicket(agent, 'Hardware open', 'hardware')
  const softwareOpen = await createTicket(agent, 'Software open', 'software')
  const hardwareProgress = await createTicket(agent, 'Hardware progress', 'hardware')
  const networkResolved = await createTicket(agent, 'Network resolved', 'network')

  const support = request.agent(app)
  await UserModel.create({ name: 'Support', email: 'filter-support@example.com', passwordHash: await bcrypt.hash('password123', 12), role: 'support' })
  assert.equal((await support.post('/auth/login').send({ email: 'filter-support@example.com', password: 'password123' })).status, 204)
  assert.equal((await support.patch(`/tickets/${hardwareProgress}`).send({ priority: 'high', status: 'in_progress' })).status, 200)
  assert.equal((await support.patch(`/tickets/${networkResolved}`).send({ priority: 'high', status: 'resolved' })).status, 200)

  async function expectTickets(query: string, expectedIds: string[]) {
    const response = await agent.get(`/tickets?${query}`)
    assert.equal(response.status, 200)
    assert.equal(response.body.total, expectedIds.length)
    assert.deepEqual((response.body.items as { _id: string }[]).map((item) => item._id).sort(), [...expectedIds].sort())
  }

  await expectTickets('category=hardware', [hardwareOpen, hardwareProgress])
  await expectTickets('priority=high', [hardwareProgress, networkResolved])
  await expectTickets('status=in_progress', [hardwareProgress])
  await expectTickets('category=software', [softwareOpen])
  await expectTickets('category=hardware&priority=high&status=in_progress', [hardwareProgress])
})

test('GET /tickets sorts by creation time, then ID, descending', async () => {
  const { agent } = await employeeSession('ticket-sort@example.com')
  const older = await createTicket(agent, 'Older', 'other')
  const tiedFirst = await createTicket(agent, 'Tied first', 'other')
  const tiedSecond = await createTicket(agent, 'Tied second', 'other')
  const oldTime = new Date('2024-01-01T00:00:00.000Z')
  const newTime = new Date('2024-01-02T00:00:00.000Z')
  for (const [id, createdAt] of [[older, oldTime], [tiedFirst, newTime], [tiedSecond, newTime]] as const) {
    await TicketModel.collection.updateOne({ _id: new mongoose.Types.ObjectId(id) }, { $set: { createdAt } })
  }

  const response = await agent.get('/tickets')
  assert.equal(response.status, 200)
  assert.equal(response.body.total, 3)
  const tiedDescending = [tiedFirst, tiedSecond].sort().reverse()
  assert.deepEqual((response.body.items as { _id: string }[]).map((item) => item._id), [...tiedDescending, older])
})

test('DELETE /tickets/:id lets the owner delete an open ticket', async () => {
  const { agent } = await employeeSession('ticket-delete@example.com')
  const ticketId = await createTicket(agent, 'Delete my ticket', 'other')
  assert.equal((await agent.delete(`/tickets/${ticketId}`)).status, 204)
  assert.equal((await agent.get(`/tickets/${ticketId}`)).status, 404)
})

test('admins manage teams and user memberships through the API', async () => {
  await UserModel.create({ name: 'Teams admin', email: 'teams-admin@example.com', passwordHash: await bcrypt.hash('password123', 12), role: 'admin' })
  const admin = request.agent(app)
  assert.equal((await admin.post('/auth/login').send({ email: 'teams-admin@example.com', password: 'password123' })).status, 204)
  const { agent: employee } = await employeeSession('team-member@example.com')
  assert.equal((await request(app).get('/teams')).status, 401)
  assert.equal((await employee.get('/teams')).status, 403)
  assert.equal((await employee.post('/teams').send({ name: 'IT', responsibilities: 'Apps' })).status, 403)

  const created = await admin.post('/teams').send({ name: '  IT  ', responsibilities: '  Maintains applications.  ' })
  assert.equal(created.status, 201)
  assert.equal(created.body.name, 'IT')
  assert.equal(created.body.responsibilities, 'Maintains applications.')
  const teamId = created.body._id as string
  const updated = await admin.patch(`/teams/${teamId}`).send({ responsibilities: 'Maintains applications and networks.' })
  assert.equal(updated.status, 200)
  assert.equal(updated.body.responsibilities, 'Maintains applications and networks.')
  assert.ok((await admin.get('/teams')).body.some((team: { _id: string }) => team._id === teamId))
  assert.equal((await admin.post('/teams').send({ name: '', responsibilities: 'Apps' })).status, 400)
  assert.equal((await admin.patch(`/teams/${teamId}`).send({})).status, 400)

  const member = await admin.post('/users').send({ name: 'Member', email: 'assigned-member@example.com', password: 'password123', role: 'employee', teamId })
  assert.equal(member.status, 201)
  assert.equal(member.body.teamId, teamId)
  assert.equal(String((await UserModel.findById(member.body._id))!.teamId), teamId)
  assert.equal((await admin.patch(`/users/${member.body._id}`).send({ teamId: '000000000000000000000001' })).status, 400)
  const removed = await admin.patch(`/users/${member.body._id}`).send({ teamId: null })
  assert.equal(removed.status, 200)
  assert.equal(removed.body.teamId, null)
  assert.equal((await employee.patch('/users/me').send({ teamId })).status, 400)
})

test('ticket creation and edits coordinate in the background and retain results on failure', async (t) => {
  const { env } = await import('../src/config/env.js')
  const originalUrl = env.AGENT_BASE_URL
  env.AGENT_BASE_URL = 'http://agent.test'
  t.after(() => { env.AGENT_BASE_URL = originalUrl })
  const { agent, userId } = await employeeSession('coordination-owner@example.com')
  const team = await TeamModel.create({ name: 'Payroll IT', responsibilities: 'Maintains payroll.' })
  await UserModel.findByIdAndUpdate(userId, { teamId: team._id })
  let finish!: (response: Response) => void
  let nextResponse = new Promise<Response>((resolve) => { finish = resolve })
  const sentBodies: { ticketId: string }[] = []
  t.mock.method(globalThis, 'fetch', async (_url: string, options: RequestInit) => {
    sentBodies.push(JSON.parse(options.body as string))
    return nextResponse
  })

  const created = await agent.post('/tickets').send({ title: 'Payroll unavailable', description: 'Finance cannot approve salaries.', category: 'software' })
  assert.equal(created.status, 201)
  assert.equal(created.body.coordination, null)
  const ticketId = created.body._id as string
  const initialUpdatedAt = created.body.updatedAt
  const result = {
    ticketId, summary: 'Payroll is unavailable.',
    relevantTeams: [{ teamId: String(team._id), reason: 'Maintains payroll.' }],
    stakeholderUserIds: [userId],
  }
  finish(new Response(JSON.stringify(result)))

  async function waitForSummary(summary: string) {
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const response = await agent.get(`/tickets/${ticketId}`)
      if (response.body.coordination?.summary === summary) return response
      await new Promise((resolve) => setTimeout(resolve, 20))
    }
    assert.fail(`Coordination did not reach summary: ${summary}`)
  }

  const analyzed = await waitForSummary(result.summary)
  assert.equal(analyzed.body.updatedAt, initialUpdatedAt)
  assert.deepEqual(analyzed.body.coordination.stakeholderUserIds, [userId])
  assert.ok(analyzed.body.coordination.analyzedAt)
  nextResponse = Promise.resolve(new Response(JSON.stringify({ ...result, summary: 'Payroll access is restored.' })))
  assert.equal((await agent.patch(`/tickets/${ticketId}`).send({ description: 'Payroll access is restored.' })).status, 200)
  await waitForSummary('Payroll access is restored.')
  assert.deepEqual(sentBodies, [{ ticketId }, { ticketId }])

  const warning = new Promise<void>((resolve) => { t.mock.method(console, 'warn', () => resolve()) })
  nextResponse = Promise.resolve(new Response('{}', { status: 502 }))
  assert.equal((await agent.patch(`/tickets/${ticketId}`).send({ title: 'Payroll follow-up' })).status, 200)
  await warning
  assert.equal((await agent.get(`/tickets/${ticketId}`)).body.coordination.summary, 'Payroll access is restored.')
})

test('an older analysis cannot overwrite coordination after a ticket edit', async (t) => {
  const { env } = await import('../src/config/env.js')
  const { coordinateTicket } = await import('../src/modules/tickets/ticketCoordination.js')
  const originalUrl = env.AGENT_BASE_URL
  env.AGENT_BASE_URL = 'http://agent.test'
  t.after(() => { env.AGENT_BASE_URL = originalUrl })
  const owner = await UserModel.create({ name: 'Stale analysis owner', email: 'stale-coordination@example.com', passwordHash: 'unused-test-hash', role: 'employee' })
  const ticket = await TicketModel.create({ title: 'Old details', description: 'Original issue', category: 'other', creatorId: owner._id })
  let finish!: (response: Response) => void
  t.mock.method(globalThis, 'fetch', () => new Promise<Response>((resolve) => { finish = resolve }))
  const analysis = coordinateTicket(String(ticket._id), ticket.updatedAt)
  await TicketModel.collection.updateOne({ _id: ticket._id }, {
    $set: { description: 'New details', updatedAt: new Date(ticket.updatedAt.getTime() + 1000) },
  })
  finish(new Response(JSON.stringify({ ticketId: String(ticket._id), summary: 'Old analysis', relevantTeams: [], stakeholderUserIds: [] })))
  await analysis
  assert.equal((await TicketModel.findById(ticket._id))!.coordination, null)
})
