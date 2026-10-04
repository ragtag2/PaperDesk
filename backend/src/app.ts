import cors from 'cors'
import express from 'express'
import { env } from './config/env.js'
import { sessionMiddleware } from './config/session.js'
import { errorHandler, notFound } from './middleware/errorHandler.js'
import { authRoutes } from './modules/auth/auth.routes.js'
import { notificationsRoutes } from './modules/notifications/notifications.routes.js'
import { ticketsRoutes } from './modules/tickets/tickets.routes.js'
import { teamsRoutes } from './modules/teams/teams.routes.js'
import { usersRoutes } from './modules/users/users.routes.js'
import { HttpError } from './shared/httpError.js'

export function createApp() {
  const app = express()
  app.set('trust proxy', env.TRUST_PROXY)
  app.disable('x-powered-by')

  app.use((req, _res, next) => {
    if (['POST', 'PATCH', 'DELETE'].includes(req.method) && req.get('Origin') && req.get('Origin') !== env.FRONTEND_ORIGIN) {
      return next(new HttpError(403, 'Origin is not allowed.'))
    }
    next()
  })
  app.use(cors({
    origin: (origin, callback) => callback(null, origin === env.FRONTEND_ORIGIN),
    credentials: true,
    allowedHeaders: ['Content-Type'],
    methods: ['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
  }))
  app.use(express.json({ limit: '32kb' }))
  app.use(sessionMiddleware())
  app.use('/auth', authRoutes)
  app.use('/users', usersRoutes)
  app.use('/tickets', ticketsRoutes)
  app.use('/teams', teamsRoutes)
  app.use('/notifications', notificationsRoutes)
  app.use(notFound)
  app.use(errorHandler)
  return app
}
