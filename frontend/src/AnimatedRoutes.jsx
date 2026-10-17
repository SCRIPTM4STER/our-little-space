import { Link, Route, Routes, useLocation } from 'react-router-dom'
import App from './App.jsx'
import Rooms from './Pages/GroupRooms.jsx'
import Auth from './Pages/Auth.jsx'
import Profile from './Pages/Profile.jsx'
import ProfileEdit from './Pages/ProfileEdit.jsx'
import Messages from './Pages/Messages.jsx'
import FriendRequests from './Pages/FriendRequests.jsx'
import Notifications from './Pages/Notifications.jsx'
import ProtectedRoute from './auth/ProtectedRoute.jsx'
import Games from "./Pages/Games.jsx"
function AnimatedRoutes() {
  const location = useLocation()

  return (
    <div className="route-transition" key={location.pathname}>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/rooms" element={<ProtectedRoute><Rooms /></ProtectedRoute>} />
        <Route path="/Rooms" element={<ProtectedRoute><Rooms /></ProtectedRoute>} />
        <Route path="/games" element={<ProtectedRoute><Games /></ProtectedRoute>} />
        <Route path="/messages" element={<ProtectedRoute><Messages /></ProtectedRoute>} />
        <Route path="/friend-requests" element={<ProtectedRoute><FriendRequests /></ProtectedRoute>} />
        <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
        <Route path="/login" element={<Auth mode="login" />} />
        <Route path="/register" element={<Auth mode="register" />} />
        <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
        <Route path="/profile/edit" element={<ProtectedRoute><ProfileEdit /></ProtectedRoute>} />
        <Route path="*" element={(
          <main className="profile-page">
            <section className="profile-status" role="status">
              <h1>Page not found.</h1>
              <Link className="button button-yellow" to="/">Return home</Link>
            </section>
          </main>
        )} />
      </Routes>
    </div>
  )
}

export default AnimatedRoutes