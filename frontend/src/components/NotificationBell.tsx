import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Bell, X } from 'lucide-react'
import { useNotifications } from '../app/NotificationsContext'
import { NotificationList } from './NotificationList'
import { Alert, Button, EmptyState, LoadingScreen } from './Ui'

export function NotificationBell() {
  const { recent, unreadCount, loading, error, refresh, markAllRead } = useNotifications()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const dialog = useRef<HTMLDialogElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (open) dialog.current?.showModal()
    else if (dialog.current?.open) { dialog.current.close(); trigger.current?.focus() }
  }, [open])

  async function readAll() {
    setBusy(true); setActionError('')
    try { await markAllRead() }
    catch (reason) { setActionError(reason instanceof Error ? reason.message : 'Could not mark notifications as read.') }
    finally { setBusy(false) }
  }

  return <>
    <button ref={trigger} type="button" className="notification-bell icon-button" aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ''}`} aria-haspopup="dialog" aria-expanded={open} aria-controls="notification-panel" onClick={() => { setActionError(''); setOpen(true); void refresh() }}>
      <Bell size={23} aria-hidden="true" />{unreadCount > 0 && <span className="notification-badge" aria-hidden="true">{unreadCount > 99 ? '99+' : unreadCount}</span>}
    </button>
    <dialog ref={dialog} id="notification-panel" className="notification-dialog" aria-labelledby="notification-panel-heading" onCancel={() => setOpen(false)} onClose={() => setOpen(false)} onClick={(event) => { if (event.target === dialog.current) setOpen(false) }}>
      <div className="notification-panel paper-panel">
        <div className="notification-panel-top"><div><span className="section-kicker">KEEPING YOU IN THE LOOP</span><h2 id="notification-panel-heading">Notifications <span className="notification-unread-label">{unreadCount} unread</span></h2></div><button className="icon-button" type="button" autoFocus onClick={() => setOpen(false)} aria-label="Close notifications"><X size={20} /></button></div>
        {(error || actionError) && <Alert>{actionError || error}</Alert>}
        {error && <Button type="button" variant="quiet" onClick={() => void refresh()}>Try again</Button>}
        <div className="notification-panel-list">{loading ? <LoadingScreen label="Loading notifications..." /> : recent.length ? <NotificationList items={recent} onOpen={() => setOpen(false)} /> : !error && <EmptyState title="You're all caught up" description="Your ticket updates will appear here." />}</div>
        <div className="notification-panel-footer"><Button type="button" variant="quiet" disabled={!unreadCount} busy={busy} onClick={readAll}>Mark all as read</Button><Link className="notification-view-all" to="/notifications" onClick={() => setOpen(false)}>View all</Link></div>
      </div>
    </dialog>
  </>
}
