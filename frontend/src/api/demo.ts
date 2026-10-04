import type { Assignee, NewTeam, NewTicket, NewUser, NotificationFilters, NotificationPage, Page, Role, Team, TeamUpdate, Ticket, TicketCoordination, TicketFilters, TicketNotification, TicketUpdate, User, UserFilters, UserUpdate } from './types'

type DemoUser = Omit<User, 'teamId'> & { password: string; teamId?: string | null }
type DemoCoordination = Pick<TicketCoordination, 'summary' | 'stakeholderUserIds' | 'analyzedAt'> & { relevantTeams: { teamId: string; reason: string }[] }
type DemoTicket = Omit<Ticket, 'creator' | 'assignee' | 'coordination'> & { coordination?: DemoCoordination | null }
type DemoData = { users: DemoUser[]; tickets: DemoTicket[]; teams: Team[]; notifications: TicketNotification[] }

const dataKey = 'paperdesk_demo_data'
const sessionKey = 'paperdesk_demo_session'
const day = 86_400_000
const date = (daysAgo: number) => new Date(Date.now() - daysAgo * day).toISOString()

const seed: DemoData = {
  notifications: [],
  teams: [
    { _id: 'team-design', name: 'Design', responsibilities: 'Design campaigns and maintain shared creative files.', createdAt: date(60), updatedAt: date(60) },
    { _id: 'team-finance', name: 'Finance', responsibilities: 'Manage payroll, accounting, and financial reporting.', createdAt: date(60), updatedAt: date(60) },
    { _id: 'team-it', name: 'IT', responsibilities: 'Maintain office networks, devices, and application access.', createdAt: date(60), updatedAt: date(60) },
  ],
  users: [
    { _id: 'u-ava', name: 'Ava Morgan', email: 'ava@paperdesk.test', password: 'password123', role: 'employee', isActive: true, createdAt: date(48), updatedAt: date(48) },
    { _id: 'u-mia', name: 'Mia Chen', email: 'mia@paperdesk.test', password: 'password123', role: 'support', isActive: true, createdAt: date(42), updatedAt: date(42) },
    { _id: 'u-sam', name: 'Sam Rivera', email: 'sam@paperdesk.test', password: 'password123', role: 'admin', isActive: true, createdAt: date(60), updatedAt: date(60) },
    { _id: 'u-eli', name: 'Eli Brooks', email: 'eli@paperdesk.test', password: 'password123', role: 'employee', isActive: true, createdAt: date(32), updatedAt: date(32) },
  ],
  tickets: [
    { _id: 't-1048', title: 'Laptop cannot connect to office Wi-Fi', description: 'The network appears in the list, but connecting gives a “Could not join network” message. It started after this morning’s update.', category: 'network', priority: 'high', status: 'open', creatorId: 'u-ava', assigneeId: null, createdAt: date(0.3), updatedAt: date(0.3) },
    { _id: 't-1047', title: 'Need access to the design drive', description: 'Please add me to the shared design drive so I can review the latest files for the campaign.', category: 'software', priority: 'medium', status: 'in_progress', creatorId: 'u-ava', assigneeId: 'u-mia', createdAt: date(1), updatedAt: date(0.4) },
    { _id: 't-1046', title: 'External monitor keeps flickering', description: 'The monitor flickers for a few seconds every time I wake my laptop. I have tried a different cable.', category: 'hardware', priority: 'medium', status: 'open', creatorId: 'u-eli', assigneeId: 'u-mia', createdAt: date(2), updatedAt: date(2) },
    { _id: 't-1045', title: 'Password reset email never arrived', description: 'I requested a reset for the analytics tool twice but have not received the message.', category: 'software', priority: 'high', status: 'in_progress', creatorId: 'u-eli', assigneeId: 'u-sam', createdAt: date(3), updatedAt: date(1) },
    { _id: 't-1044', title: 'Printer on level two is offline', description: 'The shared printer shows as offline on every workstation in our area.', category: 'hardware', priority: 'low', status: 'resolved', creatorId: 'u-ava', assigneeId: 'u-mia', createdAt: date(5), updatedAt: date(1) },
    { _id: 't-1043', title: 'VPN connection drops after ten minutes', description: 'My remote connection works at first, then disconnects without a warning after about ten minutes.', category: 'network', priority: 'medium', status: 'resolved', creatorId: 'u-eli', assigneeId: 'u-sam', createdAt: date(8), updatedAt: date(4) },
    { _id: 't-1042', title: 'Request a new keyboard', description: 'The spacebar on my keyboard has stopped registering consistently.', category: 'hardware', priority: 'low', status: 'open', creatorId: 'u-ava', assigneeId: null, createdAt: date(10), updatedAt: date(10) },
  ],
}

seed.users.forEach((user) => {
  user.teamId = user._id === 'u-ava' ? 'team-design' : user._id === 'u-eli' ? 'team-finance' : 'team-it'
})
// A saved sample analysis; the demo does not run the Python agent.
seed.tickets[0]!.coordination = {
  summary: 'Office Wi-Fi is unavailable on Ava\'s laptop after an update, interrupting design work.',
  relevantTeams: [
    { teamId: 'team-it', reason: 'IT maintains the office network and can investigate the connection failure.' },
    { teamId: 'team-design', reason: 'Design work may be delayed while Ava cannot access the office network.' },
  ],
  stakeholderUserIds: ['u-mia', 'u-sam', 'u-ava'],
  analyzedAt: date(0.2),
}

function data(): DemoData {
  try {
    const saved = localStorage.getItem(dataKey)
    if (saved) {
      const next = JSON.parse(saved) as DemoData
      next.teams ??= structuredClone(seed.teams)
      next.notifications ??= []
      return next
    }
  } catch { /* Reset invalid sample data. */ }
  localStorage.setItem(dataKey, JSON.stringify(seed))
  return structuredClone(seed)
}

function save(next: DemoData) { localStorage.setItem(dataKey, JSON.stringify(next)) }
function publicUser(user: DemoUser): User {
  const { password: _password, ...safe } = user
  void _password
  return { ...safe, teamId: safe.teamId ?? null }
}
function fail(message: string): never { throw new Error(message) }
function current(next = data()): DemoUser {
  const id = sessionStorage.getItem(sessionKey)
  const user = next.users.find((item) => item._id === id && item.isActive)
  return user ?? fail('Your session has ended. Please sign in again.')
}
function requireAdmin(next: DemoData) {
  if (current(next).role !== 'admin') fail('Only admins can manage users and teams.')
}
function validateTeamId(next: DemoData, teamId: string | null | undefined) {
  if (teamId && !next.teams.some((team) => team._id === teamId)) fail('Team not found.')
}
function teamInput(input: NewTeam): NewTeam {
  const name = input.name.trim(); const responsibilities = input.responsibilities.trim()
  if (!name || name.length > 120 || !responsibilities || responsibilities.length > 5000) fail('Enter a team name and responsibilities within the length limits.')
  return { name, responsibilities }
}
function visible(ticket: DemoTicket, user: DemoUser) {
  return user.role !== 'employee' || ticket.creatorId === user._id || !!ticket.coordination?.stakeholderUserIds.includes(user._id)
}
function enrich(ticket: DemoTicket, next: DemoData): Ticket {
  const creator = next.users.find((user) => user._id === ticket.creatorId)
  const assignee = next.users.find((user) => user._id === ticket.assigneeId)
  if (!creator) fail('Ticket creator is missing.')
  const coordination = ticket.coordination ? {
    ...ticket.coordination,
    relevantTeams: ticket.coordination.relevantTeams.map((team) => ({ ...team, name: next.teams.find((item) => item._id === team.teamId)?.name ?? null })),
    stakeholders: ticket.coordination.stakeholderUserIds.flatMap((id) => {
      const person = next.users.find((item) => item._id === id)
      return person ? [{ _id: person._id, name: person.name }] : []
    }),
  } : null
  return { ...ticket, coordination, creator: { _id: creator._id, name: creator.name }, assignee: assignee ? { _id: assignee._id, name: assignee.name } : null }
}
function paginate<T>(items: T[], page = 1, limit = 10): Page<T> {
  const safePage = Math.max(1, page)
  return { items: items.slice((safePage - 1) * limit, safePage * limit), page: safePage, limit, total: items.length }
}

export const demo = {
  async login(email: string, password: string): Promise<User> {
    const user = data().users.find((item) => item.email === email.trim().toLowerCase() && item.password === password && item.isActive)
    if (!user) fail('Email or password is incorrect.')
    sessionStorage.setItem(sessionKey, user._id)
    return publicUser(user)
  },
  async signup(name: string, email: string, password: string): Promise<void> {
    const next = data()
    if (next.users.some((user) => user.email === email.trim().toLowerCase())) fail('An account with this email already exists.')
    next.users.push({ _id: crypto.randomUUID(), name: name.trim(), email: email.trim().toLowerCase(), password, role: 'employee', isActive: true, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() })
    save(next)
  },
  async logout(): Promise<void> { sessionStorage.removeItem(sessionKey) },
  async me(): Promise<User> { return publicUser(current()) },
  async updateMe(patch: Pick<User, 'name' | 'email'>): Promise<User> {
    const next = data(); const user = current(next)
    if (next.users.some((item) => item._id !== user._id && item.email === patch.email.trim().toLowerCase())) fail('An account with this email already exists.')
    Object.assign(user, { name: patch.name.trim(), email: patch.email.trim().toLowerCase(), updatedAt: new Date().toISOString() }); save(next)
    return publicUser(user)
  },
  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    const next = data(); const user = current(next)
    if (user.password !== currentPassword) fail('Current password is incorrect.')
    user.password = newPassword; save(next)
  },
  async tickets(filters: TicketFilters): Promise<Page<Ticket>> {
    const next = data(); const user = current(next)
    const items = next.tickets.filter((ticket) => visible(ticket, user) && (filters.involvingMe !== 'true' || ticket.coordination?.stakeholderUserIds.includes(user._id)) && (!filters.status || ticket.status === filters.status) && (!filters.priority || ticket.priority === filters.priority) && (!filters.category || ticket.category === filters.category) && (!filters.assigneeId || ticket.assigneeId === filters.assigneeId))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt)).map((ticket) => enrich(ticket, next))
    return paginate(items, filters.page, filters.limit)
  },
  async ticket(id: string): Promise<Ticket> {
    const next = data(); const user = current(next)
    const ticket = next.tickets.find((item) => item._id === id && visible(item, user))
    return ticket ? enrich(ticket, next) : fail('Ticket not found.')
  },
  async createTicket(input: NewTicket): Promise<Ticket> {
    const next = data(); const user = current(next); const now = new Date().toISOString()
    const ticket: DemoTicket = { ...input, _id: `t-${Math.floor(1000 + Math.random() * 9000)}`, priority: 'medium', status: 'open', creatorId: user._id, assigneeId: null, createdAt: now, updatedAt: now }
    next.tickets.unshift(ticket); save(next); return enrich(ticket, next)
  },
  async updateTicket(id: string, patch: TicketUpdate): Promise<Ticket> {
    const next = data(); const user = current(next)
    const ticket = next.tickets.find((item) => item._id === id && visible(item, user))
    if (!ticket) fail('Ticket not found.')
    const ownerCanEdit = ticket.creatorId === user._id && ticket.status === 'open'
    const staff = user.role === 'support' || user.role === 'admin'
    if ((patch.title !== undefined || patch.description !== undefined || patch.category !== undefined) && !ownerCanEdit && user.role !== 'admin') fail('You cannot edit this ticket.')
    if ((patch.status !== undefined || patch.priority !== undefined || patch.assigneeId !== undefined) && !staff) fail('You cannot update ticket triage.')
    const wasResolved = ticket.status === 'resolved'
    Object.assign(ticket, patch, { updatedAt: new Date().toISOString() })
    if (!wasResolved && ticket.status === 'resolved') {
      for (const userId of new Set([ticket.creatorId, ...(ticket.coordination?.stakeholderUserIds ?? [])])) {
        if (next.users.some((person) => person._id === userId && person.isActive)) next.notifications.unshift({
          _id: crypto.randomUUID(), userId, ticketId: ticket._id, ticketTitle: ticket.title,
          type: 'ticket_resolved', readAt: null, createdAt: ticket.updatedAt, ticketAvailable: true,
        })
      }
    }
    save(next); return enrich(ticket, next)
  },
  async deleteTicket(id: string): Promise<void> {
    const next = data(); const user = current(next); const ticket = next.tickets.find((item) => item._id === id && visible(item, user))
    if (!ticket || (user.role !== 'admin' && !(ticket.creatorId === user._id && ticket.status === 'open'))) fail('You cannot delete this ticket.')
    next.tickets = next.tickets.filter((item) => item._id !== id); save(next)
  },
  async assignees(): Promise<Assignee[]> {
    const next = data(); if (current(next).role === 'employee') fail('Only support and admins can view assignees.')
    return next.users.filter((user) => user.isActive && user.role !== 'employee').map(({ _id, name }) => ({ _id, name }))
  },
  async users(filters: UserFilters): Promise<Page<User>> {
    const next = data(); requireAdmin(next)
    const items = next.users.filter((user) => (!filters.role || user.role === filters.role) && (!filters.isActive || String(user.isActive) === filters.isActive) && (!filters.teamId || (filters.teamId === 'none' ? !user.teamId : user.teamId === filters.teamId))).map(publicUser)
    return paginate(items, filters.page, filters.limit)
  },
  async user(id: string): Promise<User> {
    const next = data(); requireAdmin(next)
    const user = next.users.find((item) => item._id === id)
    return user ? publicUser(user) : fail('User not found.')
  },
  async createUser(input: NewUser): Promise<User> {
    const next = data(); requireAdmin(next)
    validateTeamId(next, input.teamId)
    if (next.users.some((user) => user.email === input.email.trim().toLowerCase())) fail('An account with this email already exists.')
    const user: DemoUser = { ...input, _id: crypto.randomUUID(), email: input.email.trim().toLowerCase(), isActive: true, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
    next.users.push(user); save(next); return publicUser(user)
  },
  async updateUser(id: string, patch: UserUpdate): Promise<User> {
    const next = data(); requireAdmin(next)
    validateTeamId(next, patch.teamId)
    const user = next.users.find((item) => item._id === id)
    if (!user) fail('User not found.')
    if (id === current(next)._id && (patch.isActive === false || (patch.role && patch.role !== 'admin'))) fail('You cannot remove your own admin access.')
    if (patch.email && next.users.some((item) => item._id !== id && item.email === patch.email?.trim().toLowerCase())) fail('An account with this email already exists.')
    Object.assign(user, patch, { email: patch.email?.trim().toLowerCase() ?? user.email, updatedAt: new Date().toISOString() }); save(next)
    return publicUser(user)
  },
  async deactivateUser(id: string): Promise<void> {
    const next = data(); requireAdmin(next)
    if (current(next)._id === id) fail('You cannot deactivate your own account.')
    const user = next.users.find((item) => item._id === id)
    if (!user) fail('User not found.')
    user.isActive = false; save(next)
  },
  async teams(): Promise<Team[]> {
    const next = data(); requireAdmin(next)
    return next.teams.slice().sort((a, b) => a.name.localeCompare(b.name) || a._id.localeCompare(b._id))
  },
  async notifications(filters: NotificationFilters): Promise<NotificationPage> {
    const next = data(); const user = current(next)
    const owned = next.notifications.filter((item) => item.userId === user._id)
    const items = owned.filter((item) => !filters.unread || (filters.unread === 'true' ? !item.readAt : !!item.readAt))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt) || b._id.localeCompare(a._id))
      .map((item) => ({ ...item, ticketAvailable: next.tickets.some((ticket) => ticket._id === item.ticketId && visible(ticket, user)) }))
    return { ...paginate(items, filters.page, filters.limit), unreadCount: owned.filter((item) => !item.readAt).length }
  },
  async markNotificationRead(id: string): Promise<TicketNotification> {
    const next = data(); const user = current(next)
    const item = next.notifications.find((notification) => notification._id === id && notification.userId === user._id)
    if (!item) fail('Notification not found.')
    item.readAt ??= new Date().toISOString(); save(next)
    return { ...item, ticketAvailable: next.tickets.some((ticket) => ticket._id === item.ticketId && visible(ticket, user)) }
  },
  async markAllNotificationsRead(): Promise<void> {
    const next = data(); const user = current(next); const now = new Date().toISOString()
    next.notifications.forEach((item) => { if (item.userId === user._id) item.readAt ??= now })
    save(next)
  },
  async createTeam(input: NewTeam): Promise<Team> {
    const next = data(); requireAdmin(next)
    const now = new Date().toISOString()
    const team = { ...teamInput(input), _id: crypto.randomUUID(), createdAt: now, updatedAt: now }
    next.teams.push(team); save(next); return team
  },
  async updateTeam(id: string, patch: TeamUpdate): Promise<Team> {
    const next = data(); requireAdmin(next)
    const team = next.teams.find((item) => item._id === id)
    if (!team) fail('Team not found.')
    Object.assign(team, teamInput({ ...team, ...patch }), { updatedAt: new Date().toISOString() })
    save(next); return team
  },
}

export const demoAccounts: { role: Role; email: string; name: string }[] = [
  { role: 'employee', email: 'ava@paperdesk.test', name: 'Ava' },
  { role: 'support', email: 'mia@paperdesk.test', name: 'Mia' },
  { role: 'admin', email: 'sam@paperdesk.test', name: 'Sam' },
]
