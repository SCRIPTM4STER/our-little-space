import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { apiGet, getMediaUrl } from '../../api/client'
import { useAuth } from '../../auth/useAuth.js'

function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isActivityOpen, setIsActivityOpen] = useState(false)
  const [activityCounts, setActivityCounts] = useState({ notifications: 0, messages: 0, friend_requests: 0 })
  const { user, profile, isLoading } = useAuth()
  const location = useLocation()
  const activityRef = useRef(null)

  const closeMenu = () => {
    setIsMenuOpen(false)
    setIsActivityOpen(false)
  }
  const accountLabel = profile?.display_name || profile?.username || user?.username || 'Your profile'
  const avatarInitial = accountLabel.charAt(0).toUpperCase()

  useEffect(() => {
    if (!user || isLoading) {
      setActivityCounts({ notifications: 0, messages: 0, friend_requests: 0 })
      return undefined
    }
    const refreshActivityCounts = () => {
      apiGet('/activity/summary/')
        .then(setActivityCounts)
        .catch(() => {})
    }
    refreshActivityCounts()
    const intervalId = window.setInterval(refreshActivityCounts, 30000)
    window.addEventListener('activity-updated', refreshActivityCounts)
    return () => {
      window.clearInterval(intervalId)
      window.removeEventListener('activity-updated', refreshActivityCounts)
    }
  }, [user, isLoading, location.pathname])

  useEffect(() => {
    if (!isActivityOpen) return undefined
    function handlePointerDown(event) {
      if (!activityRef.current?.contains(event.target)) setIsActivityOpen(false)
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') setIsActivityOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isActivityOpen])

  const totalActivityCount = activityCounts.notifications + activityCounts.messages + activityCounts.friend_requests

  return (
    <nav className="Navbar wavy" aria-label="Main navigation">
      <div className="nav-inner">
        <Link className="logo" to="/" onClick={closeMenu}>
          <span className="logo-star" aria-hidden="true">✦</span>
          <span>Our Little Space</span>
        </Link>

        {user && (
          <Link
            className="profile-avatar-link"
            to="/profile"
            onClick={closeMenu}
            aria-label={`Open ${accountLabel} profile`}
          >
            {profile?.avatar ? (
              <img src={getMediaUrl(profile.avatar, profile.updated_at)} alt="" className="profile-avatar" />
            ) : (
              <span className="profile-avatar profile-avatar-fallback" aria-hidden="true">{avatarInitial}</span>
            )}
          </Link>
        )}

        <button
          className="navbar-toggle"
          type="button"
          aria-expanded={isMenuOpen}
          aria-controls="primary-navigation"
          onClick={() => setIsMenuOpen((isOpen) => !isOpen)}
        >
          <span className="sr-only">Toggle navigation</span>
          <span aria-hidden="true">{isMenuOpen ? '×' : '☰'}</span>
        </button>

        <ul
          id="primary-navigation"
          className={`nav-links${isMenuOpen ? ' is-open' : ''}`}
        >
          <li><Link to="/#home" onClick={closeMenu} aria-label="Home" title="Home"><span className="nav-icon" aria-hidden="true">⌂</span><span className="nav-label">Home</span></Link></li>
          <li><Link to="/rooms" onClick={closeMenu} aria-label="Rooms" title="Rooms"><span className="nav-icon" aria-hidden="true">▦</span><span className="nav-label">Rooms</span></Link></li>
          {user && (
            <li className="activity-menu" ref={activityRef}>
              <button
                className="activity-menu-trigger"
                type="button"
                aria-label="Social activity"
                aria-expanded={isActivityOpen}
                aria-controls="activity-menu-panel"
                title="Social activity"
                onClick={() => setIsActivityOpen((isOpen) => !isOpen)}
              >
                <span aria-hidden="true">☷</span>
                <span className="sr-only">Social activity</span>
                {totalActivityCount > 0 && <span className="activity-total-badge" aria-label={`${totalActivityCount} updates`}>{totalActivityCount}</span>}
              </button>
              {isActivityOpen && (
                <div className="activity-menu-panel" id="activity-menu-panel" aria-label="Social activity links">
                  <strong>Social activity</strong>
                  <Link to="/notifications" onClick={closeMenu}>
                    <span aria-hidden="true">◉</span><span>Notifications</span><span className="activity-count">{activityCounts.notifications}</span>
                  </Link>
                  <Link to="/messages" onClick={closeMenu}>
                    <span aria-hidden="true">✉</span><span>Messages</span><span className="activity-count">{activityCounts.messages}</span>
                  </Link>
                  <Link to="/friend-requests" onClick={closeMenu}>
                    <span aria-hidden="true">♧</span><span>Friend requests</span><span className="activity-count">{activityCounts.friend_requests}</span>
                  </Link>
                </div>
              )}
            </li>
          )}
          <li><Link to="/#games" onClick={closeMenu} aria-label="Games" title="Games"><span className="nav-icon" aria-hidden="true">✣</span><span className="nav-label">Games</span></Link></li>
          {!user && <li className="auth-nav-item"><Link to="/login" onClick={closeMenu} aria-label="Log in" title="Log in"><span className="nav-icon" aria-hidden="true">↪</span><span className="nav-label">Log in</span></Link></li>}
        </ul>
      </div>
    </nav>
  )
}

export default Navbar