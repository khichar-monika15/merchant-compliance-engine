import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'

export function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'anonymous') {
    // `replace` so a redirected user pressing Back does not bounce between guard and login.
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />
  }
  return <Outlet />
}

export function PublicOnlyRoute() {
  const { status } = useAuth()
  if (status === 'authenticated') return <Navigate to="/dashboard" replace />
  return <Outlet />
}
