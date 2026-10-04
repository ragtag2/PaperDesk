import type { RequestHandler } from 'express'
import { sessionCookieName } from '../../config/session.js'
import { authenticate, signup } from './auth.service.js'
import type { LoginInput, SignupInput } from '../users/users.schemas.js'

function regenerate(req: Parameters<RequestHandler>[0]) {
  return new Promise<void>((resolve, reject) => req.session.regenerate((error) => error ? reject(error) : resolve()))
}
function save(req: Parameters<RequestHandler>[0]) {
  return new Promise<void>((resolve, reject) => req.session.save((error) => error ? reject(error) : resolve()))
}
function destroy(req: Parameters<RequestHandler>[0]) {
  return new Promise<void>((resolve, reject) => req.session.destroy((error) => error ? reject(error) : resolve()))
}

export const signupController: RequestHandler = async (req, res) => {
  res.status(201).json(await signup(req.body as SignupInput))
}

export const loginController: RequestHandler = async (req, res) => {
  const user = await authenticate(req.body as LoginInput)
  await regenerate(req)
  req.session.userId = String(user._id)
  req.session.sessionVersion = user.sessionVersion
  await save(req)
  res.sendStatus(204)
}

export const logoutController: RequestHandler = async (req, res) => {
  await destroy(req)
  res.clearCookie(sessionCookieName, { httpOnly: true, sameSite: 'lax', secure: req.secure, path: '/' })
  res.sendStatus(204)
}
