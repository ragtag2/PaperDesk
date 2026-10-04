import { z } from 'zod'
import { paginationSchema } from '../../shared/pagination.js'

export const notificationsQuerySchema = z.strictObject({
  ...paginationSchema,
  unread: z.enum(['true', 'false']).transform((value) => value === 'true').optional(),
})
export const emptyNotificationBodySchema = z.strictObject({}).default({})
export type NotificationsQuery = z.infer<typeof notificationsQuerySchema>
