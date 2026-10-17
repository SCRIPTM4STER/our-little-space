import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

function ProtectedRoute({ children }) {
  const { isLoading, user } = useAuth()
  const location = useLocation()

  if (isLoading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

export default ProtectedRoute
