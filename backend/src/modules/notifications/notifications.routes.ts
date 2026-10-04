import { Router } from 'express'
import { requireAuth } from '../../middleware/requireAuth.js'
import { validate } from '../../middleware/validate.js'
import { emptyNotificationBodySchema, notificationsQuerySchema, type NotificationsQuery } from './notifications.schemas.js'
import { listNotifications, markAllNotificationsRead, markNotificationRead } from './notifications.service.js'

export const notificationsRoutes = Router()
notificationsRoutes.use(requireAuth)
notificationsRoutes.get('/', validate({ query: notificationsQuerySchema }), async (req, res) => {
  res.json(await listNotifications(req.auth!, req.validatedQuery as NotificationsQuery))
})
notificationsRoutes.patch('/read-all', validate({ body: emptyNotificationBodySchema }), async (req, res) => {
  await markAllNotificationsRead(req.auth!)
  res.sendStatus(204)
})
notificationsRoutes.patch('/:id/read', validate({ body: emptyNotificationBodySchema }), async (req, res) => {
  res.json(await markNotificationRead(req.params.id as string, req.auth!))
})
