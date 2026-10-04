import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { TicketNotification } from '../api/types'

interface NotificationsState {
  recent: TicketNotification[]
  unreadCount: number
  loading: boolean
  error: string
  revision: number
  refresh: () => Promise<void>
  markRead: (id: string) => Promise<void>
  markAllRead: () => Promise<void>
}

const NotificationsContext = createContext<NotificationsState | null>(null)

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [recent, setRecent] = useState<TicketNotification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const mounted = useRef(false)
  const requestId = useRef(0)

  const refresh = useCallback(async () => {
    const currentRequest = ++requestId.current
    try {
      const result = await api.notifications.list({ page: 1, limit: 5 })
      if (!mounted.current || currentRequest !== requestId.current) return
      setRecent(result.items); setUnreadCount(result.unreadCount); setError('')
      setRevision((value) => value + 1)
    } catch (reason) {
      if (mounted.current && currentRequest === requestId.current) setError(reason instanceof Error ? reason.message : 'Could not load notifications.')
    } finally {
      if (mounted.current && currentRequest === requestId.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    const check = () => { if (document.visibilityState === 'visible') void refresh() }
    const timer = window.setInterval(check, 30_000)
    window.addEventListener('focus', check)
    document.addEventListener('visibilitychange', check)
    return () => {
      mounted.current = false; requestId.current += 1
      window.clearInterval(timer); window.removeEventListener('focus', check)
      document.removeEventListener('visibilitychange', check)
    }
  }, [refresh])

  const markRead = useCallback(async (id: string) => {
    requestId.current += 1
    await api.notifications.markRead(id)
    if (mounted.current) await refresh()
  }, [refresh])

  const markAllRead = useCallback(async () => {
    requestId.current += 1
    await api.notifications.markAllRead()
    if (mounted.current) await refresh()
  }, [refresh])

  return <NotificationsContext.Provider value={{ recent, unreadCount, loading, error, revision, refresh, markRead, markAllRead }}>{children}</NotificationsContext.Provider>
}

export function useNotifications() {
  const context = useContext(NotificationsContext)
  if (!context) throw new Error('useNotifications must be used inside NotificationsProvider')
  return context
}
