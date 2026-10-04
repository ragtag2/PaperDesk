export type Role = 'employee' | 'support' | 'admin'
export type TicketStatus = 'open' | 'in_progress' | 'resolved'
export type TicketPriority = 'low' | 'medium' | 'high'
export type TicketCategory = 'hardware' | 'software' | 'network' | 'other'

export interface User {
  _id: string
  name: string
  email: string
  role: Role
  isActive: boolean
  teamId: string | null
  createdAt: string
  updatedAt: string
}

export interface Assignee {
  _id: string
  name: string
}

export interface Team {
  _id: string
  name: string
  responsibilities: string
  createdAt: string
  updatedAt: string
}

export interface TicketCoordination {
  summary: string
  relevantTeams: { teamId: string; name: string | null; reason: string }[]
  stakeholderUserIds: string[]
  stakeholders: Assignee[]
  analyzedAt: string
}

export interface Ticket {
  _id: string
  title: string
  description: string
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  creatorId: string
  assigneeId: string | null
  createdAt: string
  updatedAt: string
  creator: Assignee
  assignee: Assignee | null
  coordination: TicketCoordination | null
}

export interface Page<T> {
  items: T[]
  page: number
  limit: number
  total: number
}

export interface TicketFilters {
  page?: number
  limit?: number
  status?: TicketStatus | ''
  priority?: TicketPriority | ''
  category?: TicketCategory | ''
  assigneeId?: string
  involvingMe?: 'true' | 'false' | ''
}

export interface TicketNotification {
  _id: string
  userId: string
  ticketId: string
  ticketTitle: string
  type: 'ticket_involvement' | 'ticket_resolved'
  createdAt: string
  readAt: string | null
  ticketAvailable: boolean
}

export interface NotificationFilters {
  page?: number
  limit?: number
  unread?: 'true' | 'false' | ''
}

export interface NotificationPage extends Page<TicketNotification> {
  unreadCount: number
}

export interface UserFilters {
  page?: number
  limit?: number
  role?: Role | ''
  isActive?: 'true' | 'false' | ''
  teamId?: string
}

export interface NewTicket {
  title: string
  description: string
  category: TicketCategory
}

export type TicketUpdate = Partial<Pick<Ticket, 'title' | 'description' | 'category' | 'priority' | 'status' | 'assigneeId'>>

export interface NewUser {
  name: string
  email: string
  password: string
  role: Role
  teamId?: string | null
}

export type UserUpdate = Partial<Pick<User, 'name' | 'email' | 'role' | 'isActive' | 'teamId'>>

export type NewTeam = Pick<Team, 'name' | 'responsibilities'>
export type TeamUpdate = Partial<NewTeam>
