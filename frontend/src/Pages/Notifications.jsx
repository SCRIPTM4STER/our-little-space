import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGetPage, apiPost } from '../api/client'
import UserAvatar from '../assets/components/UserAvatar'

function notificationActor(notification) {
  if (notification.notification_type === 'room_invitation') return notification.related_object?.inviter
  if (notification.notification_type === 'friend_request_accepted') return notification.related_object?.recipient
  return notification.related_object?.sender
}

function notificationText(notification) {
  if (notification.notification_type === 'room_invitation') {
    const inviter = notificationActor(notification)
    const name = inviter?.display_name || inviter?.username || 'Someone'
    const roomName = notification.related_object?.room?.name || 'a room'
    return `${name} invited you to join "${roomName}".`
  }
  const actor = notificationActor(notification)
  const name = actor?.display_name || actor?.username || 'Someone'
  if (notification.notification_type === 'friend_request') return `${name} sent you a friend request.`
  if (notification.notification_type === 'friend_request_accepted') return `${name} accepted your friend request.`
  if (notification.notification_type === 'direct_message') return `${name} sent you a direct message.`
  return 'You have a new notification.'
}

function Notifications() {
  const [notifications, setNotifications] = useState([])
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [nextOffset, setNextOffset] = useState(0)
  const [actingInvitationId, setActingInvitationId] = useState(null)

  async function loadNotifications(offset = 0, append = false) {
    setError('')
    try {
      const page = await apiGetPage('/notifications/', offset)
      setNotifications((current) => append ? [...current, ...page.data.notifications] : page.data.notifications)
      setHasMore(page.hasMore)
      setNextOffset(page.nextOffset)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadNotifications()
  }, [])

  async function loadMoreNotifications() {
    if (isLoadingMore || !hasMore) return
    setIsLoadingMore(true)
    try {
      await loadNotifications(nextOffset, true)
    } finally {
      setIsLoadingMore(false)
    }
  }

  async function markRead(id) {
    try {
      setError('')
      await apiPost(`/notifications/${id}/read/`, {})
      await loadNotifications()
      window.dispatchEvent(new Event('activity-updated'))
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function respondToRoomInvitation(invitationId, action) {
    if (actingInvitationId) return
    setActingInvitationId(invitationId)
    setError('')
    try {
      await apiPost(`/room-invitations/${invitationId}/${action}/`, {})
      await loadNotifications()
      window.dispatchEvent(new Event('activity-updated'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setActingInvitationId(null)
    }
  }

  return (
    <div className="rooms-page">
      <section className="rooms-intro">
        <p className="eyebrow">UPDATES</p>
        <h1>Notifications.</h1>
        <p>Friend requests, replies, and the little things you might have missed.</p>
      </section>
      <section className="rooms-panel notifications-panel" aria-label="Notification inbox">
        {isLoading ? <p className="muted" role="status">Loading notifications...</p> : notifications.length === 0 ? <p className="muted">You are all caught up.</p> : (
          <ul className="notification-list">
            {notifications.map((notification) => {
              const actor = notificationActor(notification)
              return (
                <li key={notification.id} className={notification.read_at ? '' : 'unread-notification'}>
                  <span className="notification-marker" aria-hidden="true" />
                  {actor && <UserAvatar profile={actor} />}
                  <p>{notificationText(notification)}</p>
                  {notification.notification_type === 'direct_message' && <Link to="/messages">Open messages</Link>}
                  {notification.notification_type.startsWith('friend_request') && <Link to="/friend-requests">Friend requests</Link>}
                  {notification.notification_type === 'room_invitation' && notification.related_object?.status === 'pending' && (
                    <div className="room-invitation-actions">
                      <button type="button" className="mini-button success" disabled={Boolean(actingInvitationId)} onClick={() => respondToRoomInvitation(notification.related_object.id, 'accept')}>
                        {actingInvitationId === notification.related_object.id ? 'Working...' : 'Accept'}
                      </button>
                      <button type="button" className="mini-button danger" disabled={Boolean(actingInvitationId)} onClick={() => respondToRoomInvitation(notification.related_object.id, 'decline')}>Decline</button>
                    </div>
                  )}
                  {notification.notification_type === 'room_invitation' && notification.related_object?.status === 'accepted' && <Link to="/rooms">Open rooms</Link>}
                  {notification.notification_type === 'room_invitation' && notification.related_object?.status === 'declined' && <span className="request-status">Declined</span>}
                  {!notification.read_at && <button type="button" className="room-link-button" onClick={() => markRead(notification.id)}>Mark read</button>}
                </li>
              )
            })}
          </ul>
        )}
        {!isLoading && hasMore && <button type="button" className="button button-yellow" onClick={loadMoreNotifications} disabled={isLoadingMore}>{isLoadingMore ? 'Loading...' : 'Load more notifications'}</button>}
      </section>
      {error && <div className="room-feedback error-text" role="alert">{error}</div>}
    </div>
  )
}

export default Notifications