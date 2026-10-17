import { useEffect, useState } from 'react'
import { apiGet, apiGetPage, apiPost } from '../api/client'
import { useAuth } from '../auth/useAuth'
import UserAvatar from '../assets/components/UserAvatar'

function FriendRequests() {
  const { user } = useAuth()
  const [incoming, setIncoming] = useState([])
  const [outgoing, setOutgoing] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [listPages, setListPages] = useState({
    incoming: { nextOffset: 0, hasMore: false, isLoading: false },
    outgoing: { nextOffset: 0, hasMore: false, isLoading: false },
    recommendations: { nextOffset: 0, hasMore: false, isLoading: false },
  })
  const [usernameQuery, setUsernameQuery] = useState('')
  const [searchResult, setSearchResult] = useState(null)
  const [isSearching, setIsSearching] = useState(false)
  const [sendingPublicId, setSendingPublicId] = useState('')
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')

  async function loadData() {
    const [received, sent, suggested] = await Promise.all([
      apiGetPage('/friend-requests/received/'),
      apiGetPage('/friend-requests/sent/'),
      apiGetPage('/users/recommendations/'),
    ])
    setIncoming(received.data)
    setOutgoing(sent.data)
    setRecommendations(suggested.data)
    setListPages({
      incoming: { nextOffset: received.nextOffset, hasMore: received.hasMore, isLoading: false },
      outgoing: { nextOffset: sent.nextOffset, hasMore: sent.hasMore, isLoading: false },
      recommendations: { nextOffset: suggested.nextOffset, hasMore: suggested.hasMore, isLoading: false },
    })
  }

  async function loadMoreList(key, path, setItems) {
    const pageState = listPages[key]
    if (pageState.isLoading || !pageState.hasMore) return
    setListPages((current) => ({ ...current, [key]: { ...current[key], isLoading: true } }))
    try {
      const page = await apiGetPage(path, pageState.nextOffset)
      setItems((current) => [...current, ...page.data])
      setListPages((current) => ({
        ...current,
        [key]: { nextOffset: page.nextOffset, hasMore: page.hasMore, isLoading: false },
      }))
    } catch (requestError) {
      setError(requestError.message)
      setListPages((current) => ({ ...current, [key]: { ...current[key], isLoading: false } }))
    }
  }

  useEffect(() => {
    loadData().catch((requestError) => setError(requestError.message))
  }, [])

  async function sendFriendRequest(targetPublicId) {
    const recipientPublicId = targetPublicId.trim()
    if (!recipientPublicId) {
      setError('Enter a public user ID.')
      return
    }
    try {
      setError('')
      setSendingPublicId(recipientPublicId)
      await apiPost('/friend-requests/', { recipient_public_id: recipientPublicId })
      setUsernameQuery('')
      setSearchResult(null)
      setFeedback('Friend request sent.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSendingPublicId('')
    }
  }

  async function searchUser(event) {
    event.preventDefault()
    const username = usernameQuery.trim().replace(/^@/, '')
    setError('')
    setFeedback('')
    setSearchResult(null)
    if (!username) {
      setError('Enter a username to search.')
      return
    }

    try {
      setIsSearching(true)
      const result = await apiGet(`/users/search/?username=${encodeURIComponent(username)}`)
      setSearchResult(result)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSearching(false)
    }
  }

  async function respond(requestId, action) {
    try {
      setError('')
      await apiPost(`/friend-requests/${requestId}/${action}/`, {})
      setFeedback(action === 'accept' ? 'Friend request accepted.' : 'Friend request declined.')
      await loadData()
      window.dispatchEvent(new Event('activity-updated'))
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <div className="rooms-page">
      <section className="rooms-intro">
        <p className="eyebrow">YOUR PEOPLE</p>
        <h1>Friend requests.</h1>
        <p>Connect with friends here. Friendships unlock private one-to-one messages.</p>
      </section>
      <section className="social-grid friend-requests-grid">
        <div className="social-card">
          <h3>Find a friend</h3>
          <form onSubmit={searchUser} className="stacked-form text-blue-600/75">
            <label htmlFor="friend-username">Username</label>
            <input id="friend-username" value={usernameQuery} onChange={(event) => setUsernameQuery(event.target.value)} placeholder="@username" maxLength="151" autoCapitalize="none" autoCorrect="off" />
            <button type="submit" className="button button-yellow" disabled={isSearching}>{isSearching ? 'Searching...' : 'Search'}</button>
          </form>
          {searchResult && (
            <div className="friend-search-result" aria-live="polite">
              <div className="user-identity">
                <UserAvatar profile={searchResult} />
                <div className="user-identity-copy">
                  <strong>{searchResult.display_name || searchResult.username}</strong>
                  <span>@{searchResult.username}</span>
                </div>
              </div>
              {searchResult.public_id === user?.public_id ? (
                <span className="request-status">This is your account</span>
              ) : (
                <button type="button" className="mini-button success" disabled={Boolean(sendingPublicId)} onClick={() => sendFriendRequest(searchResult.public_id)}>
                  {sendingPublicId === searchResult.public_id ? 'Sending...' : 'Add friend'}
                </button>
              )}
            </div>
          )}
        </div>
        <div className="social-card text-black">
          <h3>People you may know</h3>
          {recommendations.length === 0 ? <p className="muted">Recommendations appear when users share friends or rooms.</p> : (
            <ul className="social-list">
              {recommendations.map((recommendation) => (
                <li key={recommendation.public_id}>
                  <span className="user-identity"><UserAvatar profile={recommendation} /><span>
                    {recommendation.display_name || recommendation.username}
                    <small className="recommendation-reason">
                      {recommendation.mutual_friends_count} mutual {recommendation.mutual_friends_count === 1 ? 'friend' : 'friends'}
                      {' | '}
                      {recommendation.shared_rooms_count} shared {recommendation.shared_rooms_count === 1 ? 'room' : 'rooms'}
                    </small>
                  </span></span>
                  <button
                    type="button"
                    className="mini-button success"
                    disabled={Boolean(sendingPublicId)}
                    onClick={() => sendFriendRequest(recommendation.public_id)}
                  >
                    {sendingPublicId === recommendation.public_id ? 'Sending...' : 'Add friend'}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {listPages.recommendations.hasMore && <button type="button" className="button button-yellow" onClick={() => loadMoreList('recommendations', '/users/recommendations/', setRecommendations)} disabled={listPages.recommendations.isLoading}>{listPages.recommendations.isLoading ? 'Loading...' : 'Load more suggestions'}</button>}
        </div>
        <div className="social-card">
          <div className="social-section">
            <h3>Incoming</h3>
            {incoming.length === 0 ? <p className="muted">No pending requests.</p> : (
              <ul className="social-list">
                {incoming.map((request) => <li key={request.id}><span className="user-identity"><UserAvatar profile={request.sender} /><span>{request.sender?.display_name || request.sender?.username}</span></span><div><button type="button" className="mini-button success" onClick={() => respond(request.id, 'accept')}>Accept</button><button type="button" className="mini-button danger" onClick={() => respond(request.id, 'reject')}>Decline</button></div></li>)}
              </ul>
            )}
            {listPages.incoming.hasMore && <button type="button" className="button button-yellow" onClick={() => loadMoreList('incoming', '/friend-requests/received/', setIncoming)} disabled={listPages.incoming.isLoading}>{listPages.incoming.isLoading ? 'Loading...' : 'Load more'}</button>}
          </div>
          <div className="social-section">
            <h3>Sent</h3>
            {outgoing.length === 0 ? <p className="muted">No requests sent.</p> : (
              <ul className="social-list">
                {outgoing.map((request) => <li key={request.id}><span className="user-identity"><UserAvatar profile={request.recipient} /><span>{request.recipient?.display_name || request.recipient?.username}</span></span><span className="request-status">Pending</span></li>)}
              </ul>
            )}
            {listPages.outgoing.hasMore && <button type="button" className="button button-yellow" onClick={() => loadMoreList('outgoing', '/friend-requests/sent/', setOutgoing)} disabled={listPages.outgoing.isLoading}>{listPages.outgoing.isLoading ? 'Loading...' : 'Load more'}</button>}
          </div>
        </div>
      </section>
      {(error || feedback) && <div className="room-feedback" role={error ? 'alert' : 'status'}>{error || feedback}</div>}
    </div>
  )
}

export default FriendRequests