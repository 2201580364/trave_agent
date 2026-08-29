import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAdminSession } from './AdminSessionProvider'

export function AdminSessionGuard() {
  const { principal } = useAdminSession()
  const location = useLocation()

  if (principal === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}
