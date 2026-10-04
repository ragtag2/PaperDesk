import type { RequestHandler } from 'express'
import type { CreateTicketInput, TicketsQuery, UpdateTicketInput } from './tickets.schemas.js'
import * as service from './tickets.service.js'

export const listAssigneesController: RequestHandler = async (_req, res) => {
  res.json(await service.listAssignees())
}
export const listTicketsController: RequestHandler = async (req, res) => {
  res.json(await service.listTickets(req.auth!, req.validatedQuery as TicketsQuery))
}
export const createTicketController: RequestHandler = async (req, res) => {
  res.status(201).json(await service.createTicket(req.auth!, req.body as CreateTicketInput))
}
export const getTicketController: RequestHandler = async (req, res) => {
  res.json(await service.getTicket(req.params.id as string, req.auth!))
}
export const updateTicketController: RequestHandler = async (req, res) => {
  res.json(await service.updateTicket(req.params.id as string, req.auth!, req.body as UpdateTicketInput))
}
export const deleteTicketController: RequestHandler = async (req, res) => {
  await service.deleteTicket(req.params.id as string, req.auth!)
  res.sendStatus(204)
}
