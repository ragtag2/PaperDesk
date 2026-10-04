import type { RequestHandler } from 'express'
import type { Role } from '../modules/users/user.model.js'
import { HttpError } from '../shared/httpError.js'

export function requireRole(...roles: Role[]): RequestHandler {
  return (req, _res, next) => {
    if (!req.auth || !roles.includes(req.auth.role)) return next(new HttpError(403, 'Forbidden.'))
    next()
  }
}
