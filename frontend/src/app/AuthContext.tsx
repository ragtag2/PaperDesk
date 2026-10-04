import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  refresh: () => Promise<void>
  setUser: (user: User) => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    api.auth.me().then((account) => { if (active) setUser(account) }).catch(() => { if (active) setUser(null) }).finally(() => { if (active) setLoading(false) })
    const clear = () => setUser(null)
    window.addEventListener('paperdesk:unauthorized', clear)
    return () => { active = false; window.removeEventListener('paperdesk:unauthorized', clear) }
  }, [])

  async function refresh() { setUser(await api.auth.me()) }
  async function signIn(email: string, password: string) {
    await api.auth.login(email, password)
    await refresh()
  }
  async function signOut() {
    try { await api.auth.logout() } catch { /* Local sign-out still succeeds if the server is unavailable. */ }
    finally { setUser(null) }
  }

  return <AuthContext.Provider value={{ user, loading, signIn, signOut, refresh, setUser }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
