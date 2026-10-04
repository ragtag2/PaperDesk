import bcrypt from 'bcryptjs'
import { UserModel } from '../users/user.model.js'
import type { LoginInput, SignupInput } from '../users/users.schemas.js'
import { HttpError } from '../../shared/httpError.js'
import { serializeUser } from '../../shared/serialize.js'

export async function signup(input: SignupInput) {
  const user = await UserModel.create({
    name: input.name,
    email: input.email,
    passwordHash: await bcrypt.hash(input.password, 12),
    role: 'employee',
    isActive: true,
  })
  return serializeUser(user)
}

export async function authenticate(input: LoginInput) {
  const user = await UserModel.findOne({ email: input.email }).select('+passwordHash')
  if (!user || !user.isActive || !(await bcrypt.compare(input.password, user.passwordHash))) {
    throw new HttpError(401, 'Invalid email or password.')
  }
  return user
}
