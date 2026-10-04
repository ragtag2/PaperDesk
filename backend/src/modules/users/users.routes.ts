import { Router } from 'express'
import { requireAuth } from '../../middleware/requireAuth.js'
import { requireRole } from '../../middleware/requireRole.js'
import { validate } from '../../middleware/validate.js'
import { changePasswordSchema, createUserSchema, updateMeSchema, updateUserSchema, usersQuerySchema } from './users.schemas.js'
import {
  changePasswordController, createUserController, deactivateUserController, getUserController,
  listUsersController, meController, updateMeController, updateUserController,
} from './users.controller.js'

export const usersRoutes = Router()
usersRoutes.use(requireAuth)
usersRoutes.get('/me', meController)
usersRoutes.patch('/me', validate({ body: updateMeSchema }), updateMeController)
usersRoutes.patch('/me/password', validate({ body: changePasswordSchema }), changePasswordController)
usersRoutes.use(requireRole('admin'))
usersRoutes.get('/', validate({ query: usersQuerySchema }), listUsersController)
usersRoutes.post('/', validate({ body: createUserSchema }), createUserController)
usersRoutes.get('/:id', getUserController)
usersRoutes.patch('/:id', validate({ body: updateUserSchema }), updateUserController)
usersRoutes.delete('/:id', deactivateUserController)
