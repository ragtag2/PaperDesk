import type { Role } from '../users/user.model.js'
import type { TicketRecord } from './ticket.model.js'
import type { UpdateTicketInput } from './tickets.schemas.js'
import { HttpError } from '../../shared/httpError.js'

export interface Actor { userId: string; role: Role }

export function isStaff(actor: Actor) {
  return actor.role === 'support' || actor.role === 'admin'
}

export function visibleFilter(actor: Actor) {
  return actor.role === 'employee' ? { $or: [
    { creatorId: actor.userId }, { 'coordination.stakeholderUserIds': actor.userId },
  ] } : {}
}

export function assertCanPatch(actor: Actor, ticket: TicketRecord, patch: UpdateTicketInput) {
  if (actor.role === 'admin') return
  const ownsOpen = String(ticket.creatorId) === actor.userId && ticket.status === 'open'
  const changesDetails = ['title', 'description', 'category'].some((key) => key in patch)
  const changesTriage = ['priority', 'status', 'assigneeId'].some((key) => key in patch)
  if ((changesDetails && !ownsOpen) || (changesTriage && !isStaff(actor))) {
    throw new HttpError(403, 'You cannot make this change to the ticket.')
  }
}

export function assertCanDelete(actor: Actor, ticket: TicketRecord) {
  if (actor.role !== 'admin' && !(String(ticket.creatorId) === actor.userId && ticket.status === 'open')) {
    throw new HttpError(403, 'You cannot delete this ticket.')
  }
}
