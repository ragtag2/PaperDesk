import type { TicketNotification } from '../api/types'

export function notificationTitle(type: TicketNotification['type']) {
  return type === 'ticket_resolved' ? 'Ticket resolved' : "You're involved in a ticket"
}

export function relativeNotificationTime(value: string) {
  const seconds = Math.max(0, (Date.now() - Date.parse(value)) / 1000)
  if (seconds < 60) return 'Just now'
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  if (seconds < 3600) return formatter.format(-Math.floor(seconds / 60), 'minute')
  if (seconds < 86_400) return formatter.format(-Math.floor(seconds / 3600), 'hour')
  return formatter.format(-Math.floor(seconds / 86_400), 'day')
}

export function groupNotifications(items: TicketNotification[]) {
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1)
  const groups = new Map<string, TicketNotification[]>()
  for (const item of items) {
    const created = Date.parse(item.createdAt)
    const label = created >= today.getTime() ? 'Today' : created >= yesterday.getTime() ? 'Yesterday' : 'Earlier'
    groups.set(label, [...(groups.get(label) ?? []), item])
  }
  return [...groups.entries()]
}
