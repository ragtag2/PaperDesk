import type { Role, Ticket, TicketCategory, TicketPriority, TicketStatus } from '../api/types'

export const categories: { value: TicketCategory; label: string }[] = [
  { value: 'hardware', label: 'Hardware' }, { value: 'software', label: 'Software' },
  { value: 'network', label: 'Network' }, { value: 'other', label: 'Other' },
]
export const priorities: { value: TicketPriority; label: string }[] = [
  { value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' }, { value: 'high', label: 'High' },
]
export const statuses: { value: TicketStatus; label: string }[] = [
  { value: 'open', label: 'Open' }, { value: 'in_progress', label: 'In progress' }, { value: 'resolved', label: 'Resolved' },
]

export function labelFor(value: string): string {
  return [...categories, ...priorities, ...statuses].find((item) => item.value === value)?.label ?? value
}

export function shortDate(value?: string): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

export function canEditTicket(ticket: Ticket, userId: string, role: Role): boolean {
  return role === 'admin' || (ticket.creatorId === userId && ticket.status === 'open')
}
export function canDeleteTicket(ticket: Ticket, userId: string, role: Role): boolean {
  return role === 'admin' || (ticket.creatorId === userId && ticket.status === 'open')
}
export function canTriageTicket(role: Role): boolean { return role === 'support' || role === 'admin' }
