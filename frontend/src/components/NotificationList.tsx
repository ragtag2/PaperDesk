import { useState } from 'react'
import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { Check, CircleCheck, UserRoundPlus } from 'lucide-react'
import type { TicketNotification } from '../api/types'
import { useNotifications } from '../app/NotificationsContext'
import { notificationTitle, relativeNotificationTime } from '../features/notifications'
import { Alert } from './Ui'

function NotificationItem({ item, onOpen }: { item: TicketNotification; onOpen?: () => void }) {
  const { markRead } = useNotifications()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const Icon = item.type === 'ticket_resolved' ? CircleCheck : UserRoundPlus

  async function read(openTicket: boolean) {
    setBusy(true); setError('')
    try {
      if (!item.readAt) await markRead(item._id)
      if (openTicket) { onOpen?.(); navigate(`/tickets/${item.ticketId}`) }
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not mark this notification as read.') }
    finally { setBusy(false) }
  }

  function open(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return
    event.preventDefault()
    if (!busy) void read(true)
  }

  const content = <>
    <span className="notification-icon" aria-hidden="true"><Icon size={21} /></span>
    <span className="notification-copy"><strong>{notificationTitle(item.type)}</strong><span className="notification-ticket">{item.ticketTitle}</span><span className="notification-meta">{!item.readAt && <span className="notification-dot"><span className="sr-only">Unread</span></span>}<time dateTime={item.createdAt} title={new Date(item.createdAt).toLocaleString()}>{relativeNotificationTime(item.createdAt)}</time>{!item.ticketAvailable && <span>Ticket no longer available</span>}</span></span>
  </>
  return <li className={`notification-item ${item.readAt ? 'notification-read' : 'notification-unread'}`}>
    <div className="notification-row">
      {item.ticketAvailable ? <Link className="notification-link" to={`/tickets/${item.ticketId}`} onClick={open} aria-busy={busy}>{content}</Link> : <div className="notification-link notification-unavailable">{content}</div>}
      {!item.readAt && <button className="icon-button notification-mark" type="button" disabled={busy} onClick={() => void read(false)} aria-label={`Mark notification for ${item.ticketTitle} as read`} title="Mark as read"><Check size={19} /></button>}
    </div>
    {error && <Alert>{error}</Alert>}
  </li>
}

export function NotificationList({ items, onOpen }: { items: TicketNotification[]; onOpen?: () => void }) {
  return <ul className="notification-list">{items.map((item) => <NotificationItem key={item._id} item={item} onOpen={onOpen} />)}</ul>
}
