import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router'
import { useAuth } from './AuthContext'
import { AppLayout } from './AppLayout'
import { LoginPage } from '../pages/LoginPage'
import { SignUpPage } from '../pages/SignUpPage'
import { TicketsPage } from '../pages/TicketsPage'
import { CreateTicketPage } from '../pages/CreateTicketPage'
import { TicketDetailsPage } from '../pages/TicketDetailsPage'
import { ProfilePage } from '../pages/ProfilePage'
import { UsersPage } from '../pages/UsersPage'
import { TeamsPage } from '../pages/TeamsPage'
import { NotificationsPage } from '../pages/NotificationsPage'
import { LoadingScreen } from '../components/Ui'

function Protected() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <LoadingScreen />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

function AdminOnly() {
  const { user } = useAuth()
  return user?.role === 'admin' ? <Outlet /> : <Navigate to="/tickets" replace />
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingScreen />
  return user ? <Navigate to="/tickets" replace /> : children
}

export function App() {
  return <Routes>
    <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
    <Route path="/signup" element={<PublicOnly><SignUpPage /></PublicOnly>} />
    <Route element={<Protected />}>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/tickets" replace />} />
        <Route path="tickets" element={<TicketsPage />} />
        <Route path="tickets/new" element={<CreateTicketPage />} />
        <Route path="tickets/:id" element={<TicketDetailsPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route element={<AdminOnly />}>
          <Route path="users" element={<UsersPage />} />
          <Route path="teams" element={<TeamsPage />} />
        </Route>
      </Route>
    </Route>
    <Route path="*" element={<Navigate to="/tickets" replace />} />
  </Routes>
}
