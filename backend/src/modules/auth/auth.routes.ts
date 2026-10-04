import { Router } from 'express'
import { requireAuth } from '../../middleware/requireAuth.js'
import { validate } from '../../middleware/validate.js'
import { loginSchema, signupSchema } from '../users/users.schemas.js'
import { loginController, logoutController, signupController } from './auth.controller.js'

export const authRoutes = Router()
authRoutes.post('/signup', validate({ body: signupSchema }), signupController)
authRoutes.post('/login', validate({ body: loginSchema }), loginController)
authRoutes.post('/logout', requireAuth, logoutController)
