import { z } from 'zod'
import { objectIdSchema } from '../../shared/objectId.js'
import { paginationSchema } from '../../shared/pagination.js'
import { categories, priorities, statuses } from './ticket.model.js'

const title = z.string().trim().min(1).max(120)
const description = z.string().trim().min(1).max(5000)

export const createTicketSchema = z.strictObject({
  title,
  description,
  category: z.enum(categories),
})
export const updateTicketSchema = z.strictObject({
  title,
  description,
  category: z.enum(categories),
  priority: z.enum(priorities),
  status: z.enum(statuses),
  assigneeId: objectIdSchema.nullable(),
}).partial().refine((value) => Object.keys(value).length > 0, 'Provide at least one field.')
export const ticketsQuerySchema = z.strictObject({
  ...paginationSchema,
  status: z.enum(statuses).optional(),
  priority: z.enum(priorities).optional(),
  category: z.enum(categories).optional(),
  assigneeId: objectIdSchema.optional(),
  involvingMe: z.enum(['true', 'false']).transform((value) => value === 'true').optional(),
})

export type CreateTicketInput = z.infer<typeof createTicketSchema>
export type UpdateTicketInput = z.infer<typeof updateTicketSchema>
export type TicketsQuery = z.infer<typeof ticketsQuerySchema>
