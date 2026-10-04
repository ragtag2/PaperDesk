import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { api } from '../api/client'
import type { NotificationPage } from '../api/types'
import { useNotifications } from '../app/NotificationsContext'
import { NotificationList } from '../components/NotificationList'
import { Alert, Button, EmptyState, LoadingScreen, PageHeading, Pagination } from '../components/Ui'
import { groupNotifications } from '../features/notifications'

export function NotificationsPage() {
  const { unreadCount, revision, markAllRead, refresh } = useNotifications()
  const [searchParams, setSearchParams] = useSearchParams()
  const [result, setResult] = useState<NotificationPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const unread = searchParams.get('unread') === 'true'
  const page = Math.max(1, Math.floor(Number(searchParams.get('page')) || 1))

  useEffect(() => {
    let active = true
    api.notifications.list({ page, limit: 15, unread: unread ? 'true' : undefined }).then((data) => {
      if (active) { setResult(data); setError('') }
    }).catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : 'Could not load notifications.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, unread, revision, retry])

  useEffect(() => {
    if (!result || result.page !== page || page <= Math.max(1, Math.ceil(result.total / result.limit))) return
    const next = new URLSearchParams(searchParams); next.set('page', String(Math.max(1, Math.ceil(result.total / result.limit))))
    setSearchParams(next, { replace: true })
  }, [result, page, searchParams, setSearchParams])

  function filter(onlyUnread: boolean) {
    if (onlyUnread === unread && page === 1) return
    setLoading(true); setResult(null)
    setSearchParams(onlyUnread ? { unread: 'true' } : {})
  }

  async function readAll() {
    setBusy(true); setError('')
    try { await markAllRead() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not mark notifications as read.') }
    finally { setBusy(false) }
  }

  return <div className="notifications-page">
    <PageHeading eyebrow="YOUR ACTIVITY" title="Notifications" description="Ticket updates that matter to you, all in one place." />
    <section className="paper-panel notifications-history" aria-label="Notification history">
      <div className="notifications-toolbar"><div className="notification-filters" aria-label="Filter notifications"><button type="button" aria-pressed={!unread} className={!unread ? 'selected' : ''} onClick={() => filter(false)}>All</button><button type="button" aria-pressed={unread} className={unread ? 'selected' : ''} onClick={() => filter(true)}>Unread <span>{unreadCount}</span></button></div><Button type="button" variant="quiet" busy={busy} disabled={!unreadCount} onClick={readAll}>Mark all as read</Button></div>
      {error && <div className="notifications-feedback"><Alert>{error}</Alert><Button type="button" variant="quiet" onClick={() => { setRetry((value) => value + 1); void refresh() }}>Try again</Button></div>}
      {loading ? <LoadingScreen label="Loading notifications..." /> : result?.items.length ? <>
        {groupNotifications(result.items).map(([label, items]) => <section key={label} className="notification-group" aria-label={label}><h2>{label}</h2><NotificationList items={items} /></section>)}
        <Pagination page={result.page} limit={result.limit} total={result.total} onPage={(nextPage) => { const next = new URLSearchParams(searchParams); next.set('page', String(nextPage)); setSearchParams(next); setLoading(true) }} />
      </> : !error && <EmptyState title="You're all caught up" description={unread ? 'No unread notifications. You can view your previous updates in All.' : 'When you become involved in a ticket, your updates will appear here.'} />}
    </section>
  </div>
}
