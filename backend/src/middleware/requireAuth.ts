import type { RequestHandler } from 'express'
import { UserModel } from '../modules/users/user.model.js'
import { HttpError } from '../shared/httpError.js'

export const requireAuth: RequestHandler = async (req, _res, next) => {
  try {
    const userId = req.session.userId
    if (!userId) throw new HttpError(401, 'Please sign in.')
    const user = await UserModel.findById(userId).select('role isActive sessionVersion').lean()
    if (!user || !user.isActive || user.sessionVersion !== req.session.sessionVersion) {
      throw new HttpError(401, 'Please sign in.')
    }
    req.auth = { userId, role: user.role }
    next()
  } catch (error) { next(error) }
}
