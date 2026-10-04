import { Router } from 'express'
import { requireAuth } from '../../middleware/requireAuth.js'
import { requireRole } from '../../middleware/requireRole.js'
import { validate } from '../../middleware/validate.js'
import { createTicketSchema, ticketsQuerySchema, updateTicketSchema } from './tickets.schemas.js'
import {
  createTicketController, deleteTicketController, getTicketController, listAssigneesController,
  listTicketsController, updateTicketController,
} from './tickets.controller.js'

export const ticketsRoutes = Router()
ticketsRoutes.use(requireAuth)
ticketsRoutes.get('/assignees', requireRole('support', 'admin'), listAssigneesController)
ticketsRoutes.get('/', validate({ query: ticketsQuerySchema }), listTicketsController)
ticketsRoutes.post('/', validate({ body: createTicketSchema }), createTicketController)
ticketsRoutes.get('/:id', getTicketController)
ticketsRoutes.patch('/:id', validate({ body: updateTicketSchema }), updateTicketController)
ticketsRoutes.delete('/:id', deleteTicketController)
