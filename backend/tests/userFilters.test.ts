import assert from 'node:assert/strict'
import { test } from 'node:test'
import { Types } from 'mongoose'

process.env.MONGODB_URI = 'mongodb://127.0.0.1:27018'
process.env.SESSION_SECRET = 'user-filters-test-secret-with-at-least-32-characters'

const { usersQuerySchema } = await import('../src/modules/users/users.schemas.js')
const { UserModel } = await import('../src/modules/users/user.model.js')
const { listUsers } = await import('../src/modules/users/users.service.js')
const teamId = new Types.ObjectId()

test('user queries validate team IDs and the no-team filter alongside existing filters', () => {
  assert.deepEqual(usersQuerySchema.parse({ teamId: String(teamId), isActive: 'true', role: 'employee' }), {
    teamId: String(teamId), isActive: true, role: 'employee', page: 1, limit: 10,
  })
  assert.equal(usersQuerySchema.parse({ teamId: 'none' }).teamId, 'none')
  for (const value of ['invalid', '', 'null', ['none'], { $ne: null }]) {
    assert.equal(usersQuerySchema.safeParse({ teamId: value }).success, false)
  }
})

test('user list applies team, role, and active filters to both items and total before pagination', async (t) => {
  const person = {
    _id: new Types.ObjectId(), name: 'Team member', email: 'member@example.com', role: 'employee', isActive: true, teamId,
    createdAt: new Date('2026-10-02T08:00:00Z'), updatedAt: new Date('2026-10-02T08:00:00Z'),
  }
  const find = t.mock.method(UserModel, 'find', () => ({ sort: () => ({ skip: (offset: number) => {
    assert.equal(offset, 10)
    return { limit: (limit: number) => { assert.equal(limit, 10); return { lean: async () => [person] } } }
  } }) }))
  const count = t.mock.method(UserModel, 'countDocuments', async () => 11)

  const result = await listUsers(usersQuerySchema.parse({ teamId: String(teamId), role: 'employee', isActive: 'true', page: '2' }))

  assert.deepEqual(find.mock.calls[0]!.arguments[0], { teamId, role: 'employee', isActive: true })
  assert.deepEqual(count.mock.calls[0]!.arguments[0], find.mock.calls[0]!.arguments[0])
  assert.equal(result.total, 11)
  assert.equal(result.page, 2)
  assert.equal(result.items[0]!.teamId, String(teamId))
  assert.equal('passwordHash' in result.items[0]!, false)
})

test('available-member queries select active users with null or missing membership', async (t) => {
  const find = t.mock.method(UserModel, 'find', () => ({ sort: () => ({ skip: () => ({ limit: () => ({ lean: async () => [] }) }) }) }))
  const count = t.mock.method(UserModel, 'countDocuments', async () => 0)

  await listUsers(usersQuerySchema.parse({ teamId: 'none', isActive: 'true' }))
  assert.deepEqual(find.mock.calls[0]!.arguments[0], { teamId: null, isActive: true })
  assert.deepEqual(count.mock.calls[0]!.arguments[0], find.mock.calls[0]!.arguments[0])

  await listUsers(usersQuerySchema.parse({}))
  assert.deepEqual(find.mock.calls[1]!.arguments[0], {})
})
