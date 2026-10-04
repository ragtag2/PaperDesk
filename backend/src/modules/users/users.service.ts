import bcrypt from 'bcryptjs'
import { UserModel } from './user.model.js'
import type { ChangePasswordInput, CreateUserInput, UpdateMeInput, UpdateUserInput, UsersQuery } from './users.schemas.js'
import { HttpError } from '../../shared/httpError.js'
import { objectId } from '../../shared/objectId.js'
import { pageResult } from '../../shared/pagination.js'
import { serializeUser } from '../../shared/serialize.js'
import { resolveTeamId } from '../teams/teams.service.js'

export async function getMe(userId: string) {
  const user = await UserModel.findById(userId)
  if (!user) throw new HttpError(401, 'Please sign in.')
  return serializeUser(user)
}

export async function updateMe(userId: string, patch: UpdateMeInput) {
  const user = await UserModel.findById(userId)
  if (!user) throw new HttpError(401, 'Please sign in.')
  Object.assign(user, patch)
  await user.save()
  return serializeUser(user)
}

export async function changePassword(userId: string, input: ChangePasswordInput) {
  const user = await UserModel.findById(userId).select('+passwordHash')
  if (!user) throw new HttpError(401, 'Please sign in.')
  if (!(await bcrypt.compare(input.currentPassword, user.passwordHash))) {
    throw new HttpError(400, 'Current password is incorrect.')
  }
  user.passwordHash = await bcrypt.hash(input.newPassword, 12)
  await user.save()
}

export async function listUsers(query: UsersQuery) {
  const filter = {
    ...(query.role ? { role: query.role } : {}),
    ...(query.isActive !== undefined ? { isActive: query.isActive } : {}),
    ...(query.teamId ? { teamId: query.teamId === 'none' ? null : objectId(query.teamId) } : {}),
  }
  const [items, total] = await Promise.all([
    UserModel.find(filter).sort({ createdAt: -1, _id: -1 }).skip((query.page - 1) * query.limit).limit(query.limit).lean(),
    UserModel.countDocuments(filter),
  ])
  return pageResult(items.map(serializeUser), query.page, query.limit, total)
}

export async function createUser(input: CreateUserInput) {
  const teamId = await resolveTeamId(input.teamId ?? null)
  const user = await UserModel.create({
    name: input.name,
    email: input.email,
    passwordHash: await bcrypt.hash(input.password, 12),
    role: input.role,
    isActive: true,
    teamId,
  })
  return serializeUser(user)
}

export async function getUser(id: string) {
  const user = await UserModel.findById(objectId(id))
  if (!user) throw new HttpError(404, 'User not found.')
  return serializeUser(user)
}

export async function updateUser(id: string, actorId: string, patch: UpdateUserInput) {
  const user = await UserModel.findById(objectId(id))
  if (!user) throw new HttpError(404, 'User not found.')
  if (String(user._id) === actorId && (patch.isActive === false || (patch.role !== undefined && patch.role !== 'admin'))) {
    throw new HttpError(403, 'You cannot remove your own admin access.')
  }
  if (patch.isActive === false && user.isActive) user.sessionVersion += 1
  Object.assign(user, {
    ...patch,
    ...(patch.teamId !== undefined ? { teamId: await resolveTeamId(patch.teamId) } : {}),
  })
  await user.save()
  return serializeUser(user)
}

export async function deactivateUser(id: string, actorId: string) {
  const user = await UserModel.findById(objectId(id))
  if (!user) throw new HttpError(404, 'User not found.')
  if (String(user._id) === actorId) throw new HttpError(403, 'You cannot deactivate your own account.')
  if (user.isActive) {
    user.isActive = false
    user.sessionVersion += 1
    await user.save()
  }
}
