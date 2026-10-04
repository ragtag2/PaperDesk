import { demo } from './demo'
import type { Assignee, NewTeam, NewTicket, NewUser, NotificationFilters, NotificationPage, Page, Team, TeamUpdate, Ticket, TicketFilters, TicketNotification, TicketUpdate, User, UserFilters, UserUpdate } from './types'

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000').replace(/\/$/, '')

// Development opens with sample data unless explicitly connected to a backend.
export const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true' || (import.meta.env.DEV && !import.meta.env.VITE_API_BASE_URL && import.meta.env.VITE_DEMO_MODE !== 'false')

function params(values: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) if (value !== undefined && value !== '') query.set(key, String(value))
  const result = query.toString()
  return result ? `?${result}` : ''
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
      credentials: 'include',
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    })
  } catch {
    throw new Error('Could not reach the server. Check your connection and try again.')
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}). Please try again.`
    try {
      const body = await response.json() as { message?: string }
      message = body.message || message
    } catch { /* Keep the status-based message. */ }
    if (response.status === 401 && path !== '/auth/login') window.dispatchEvent(new Event('paperdesk:unauthorized'))
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  const text = await response.text()
  return text ? JSON.parse(text) as T : undefined as T
}

function json(method: string, body: unknown): RequestInit { return { method, body: JSON.stringify(body) } }

export const api = {
  auth: {
    async login(email: string, password: string): Promise<void> {
      if (isDemoMode) { await demo.login(email, password); return }
      await request<void>('/auth/login', json('POST', { email, password }))
    },
    async signup(name: string, email: string, password: string): Promise<void> {
      if (isDemoMode) return demo.signup(name, email, password)
      await request('/auth/signup', json('POST', { name, email, password }))
    },
    async logout(): Promise<void> {
      if (isDemoMode) await demo.logout()
      else await request('/auth/logout', { method: 'POST' })
    },
    me(): Promise<User> { return isDemoMode ? demo.me() : request('/users/me') },
  },
  profile: {
    update(name: string, email: string): Promise<User> { return isDemoMode ? demo.updateMe({ name, email }) : request('/users/me', json('PATCH', { name, email })) },
    changePassword(currentPassword: string, newPassword: string): Promise<void> {
      return isDemoMode ? demo.changePassword(currentPassword, newPassword) : request('/users/me/password', json('PATCH', { currentPassword, newPassword }))
    },
  },
  tickets: {
    list(filters: TicketFilters): Promise<Page<Ticket>> { return isDemoMode ? demo.tickets(filters) : request(`/tickets${params(filters as Record<string, string | number | undefined>)}`) },
    get(id: string): Promise<Ticket> { return isDemoMode ? demo.ticket(id) : request(`/tickets/${encodeURIComponent(id)}`) },
    create(input: NewTicket): Promise<Ticket> { return isDemoMode ? demo.createTicket(input) : request('/tickets', json('POST', input)) },
    update(id: string, patch: TicketUpdate): Promise<Ticket> { return isDemoMode ? demo.updateTicket(id, patch) : request(`/tickets/${encodeURIComponent(id)}`, json('PATCH', patch)) },
    remove(id: string): Promise<void> { return isDemoMode ? demo.deleteTicket(id) : request(`/tickets/${encodeURIComponent(id)}`, { method: 'DELETE' }) },
    assignees(): Promise<Assignee[]> { return isDemoMode ? demo.assignees() : request('/tickets/assignees') },
  },
  users: {
    list(filters: UserFilters): Promise<Page<User>> { return isDemoMode ? demo.users(filters) : request(`/users${params(filters as Record<string, string | number | undefined>)}`) },
    create(input: NewUser): Promise<User> { return isDemoMode ? demo.createUser(input) : request('/users', json('POST', input)) },
    get(id: string): Promise<User> { return isDemoMode ? demo.user(id) : request(`/users/${encodeURIComponent(id)}`) },
    update(id: string, patch: UserUpdate): Promise<User> { return isDemoMode ? demo.updateUser(id, patch) : request(`/users/${encodeURIComponent(id)}`, json('PATCH', patch)) },
    deactivate(id: string): Promise<void> { return isDemoMode ? demo.deactivateUser(id) : request(`/users/${encodeURIComponent(id)}`, { method: 'DELETE' }) },
  },
  teams: {
    list(): Promise<Team[]> { return isDemoMode ? demo.teams() : request('/teams') },
    create(input: NewTeam): Promise<Team> { return isDemoMode ? demo.createTeam(input) : request('/teams', json('POST', input)) },
    update(id: string, patch: TeamUpdate): Promise<Team> { return isDemoMode ? demo.updateTeam(id, patch) : request(`/teams/${encodeURIComponent(id)}`, json('PATCH', patch)) },
  },
  notifications: {
    list(filters: NotificationFilters = {}): Promise<NotificationPage> { return isDemoMode ? demo.notifications(filters) : request(`/notifications${params(filters as Record<string, string | number | undefined>)}`) },
    markRead(id: string): Promise<TicketNotification> { return isDemoMode ? demo.markNotificationRead(id) : request(`/notifications/${encodeURIComponent(id)}/read`, { method: 'PATCH' }) },
    markAllRead(): Promise<void> { return isDemoMode ? demo.markAllNotificationsRead() : request('/notifications/read-all', { method: 'PATCH' }) },
  },
}
