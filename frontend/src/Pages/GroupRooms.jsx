import { useEffect, useRef, useState } from 'react'
import { apiDelete, apiGet, apiGetPage, apiPost, getWebSocketUrl } from '../api/client'
import { useAuth } from '../auth/useAuth'
import UserAvatar from '../assets/components/UserAvatar'
import { mergeMessages, MESSAGE_HISTORY_PAGE_SIZE, MESSAGE_POLL_INTERVAL_MS } from '../utils/messages'

let youtubeIframeApiPromise

function loadYoutubeIframeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT)
  if (youtubeIframeApiPromise) return youtubeIframeApiPromise

  youtubeIframeApiPromise = new Promise((resolve, reject) => {
    const previousReadyHandler = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      try {
        previousReadyHandler?.()
      } finally {
        resolve(window.YT)
      }
    }

    let script = document.querySelector('script[src="https://www.youtube.com/iframe_api"]')
    if (!script) {
      script = document.createElement('script')
      script.src = 'https://www.youtube.com/iframe_api'
      script.async = true
      document.head.appendChild(script)
    }
    script.onerror = () => {
      youtubeIframeApiPromise = undefined
      reject(new Error('The YouTube player could not be loaded.'))
    }
  })

  return youtubeIframeApiPromise
}

function getYoutubeVideoId(videoUrl) {
  if (!videoUrl) return ''
  try {
    const parsedUrl = new URL(videoUrl)
    const hostname = parsedUrl.hostname.toLowerCase().replace(/^www\./, '')
    const videoIdFromPath = (pathname) => {
      const match = pathname.match(/(?:\/embed\/|\/v\/|\/shorts\/|\/watch\?v=)?([A-Za-z0-9_-]{11})/)
      return match ? match[1] : ''
    }

    if (hostname === 'youtu.be') return videoIdFromPath(parsedUrl.pathname)
    if (hostname.includes('youtube')) return parsedUrl.searchParams.get('v') || videoIdFromPath(parsedUrl.pathname)
  } catch {
    return ''
  }
  return ''
}

function GroupRooms() {
  const { user, profile } = useAuth()
  const [rooms, setRooms] = useState([])
  const [roomNextOffset, setRoomNextOffset] = useState(0)
  const [hasMoreRooms, setHasMoreRooms] = useState(false)
  const [isLoadingMoreRooms, setIsLoadingMoreRooms] = useState(false)
  const [selectedRoomId, setSelectedRoomId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isLoadingOlderMessages, setIsLoadingOlderMessages] = useState(false)
  const [hasOlderMessages, setHasOlderMessages] = useState(false)
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [roomName, setRoomName] = useState('')
  const [messageDraft, setMessageDraft] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [isInviteOpen, setIsInviteOpen] = useState(false)
  const [inviteFriends, setInviteFriends] = useState([])
  const [inviteFriendNextOffset, setInviteFriendNextOffset] = useState(0)
  const [hasMoreInviteFriends, setHasMoreInviteFriends] = useState(false)
  const [isLoadingMoreInviteFriends, setIsLoadingMoreInviteFriends] = useState(false)
  const [roomMemberIds, setRoomMemberIds] = useState([])
  const [pendingInviteeIds, setPendingInviteeIds] = useState([])
  const [inviteSearch, setInviteSearch] = useState('')
  const [inviteLoading, setInviteLoading] = useState(false)
  const [sendingInviteId, setSendingInviteId] = useState('')
  const [inviteError, setInviteError] = useState('')
  const [inviteFeedback, setInviteFeedback] = useState('')
  const [isCreatingRoom, setIsCreatingRoom] = useState(false)
  const messagesRef = useRef([])
  const chatWindowRef = useRef(null)
  const previousScrollPositionRef = useRef(null)
  const [watchState, setWatchState] = useState(null)
  const [watchVideoInput, setWatchVideoInput] = useState('')
  const [watchIsLoading, setWatchIsLoading] = useState(false)
  const [watchError, setWatchError] = useState('')
  const [watchSocketReady, setWatchSocketReady] = useState(false)
  const [watchTimeline, setWatchTimeline] = useState({ position: 0, duration: 0 })
  const [watchSeekPosition, setWatchSeekPosition] = useState(null)
  const watchSocketRef = useRef(null)
  const watchPlayerContainerRef = useRef(null)
  const watchPlayerRef = useRef(null)
  const watchPlayerReadyRef = useRef(false)
  const watchPlayerVideoIdRef = useRef('')
  const watchStateRef = useRef(watchState)
  const selectedRoom = rooms.find((room) => room.id === selectedRoomId && room.is_member)
  const canControlWatch = Boolean(
    selectedRoom?.is_owner || watchState?.controller?.public_id === user?.public_id,
  )
  const youtubeVideoId = getYoutubeVideoId(watchState?.video_url)

  function getWatchSocketUrl(roomId) {
    return getWebSocketUrl(`/ws/watch/${roomId}/`)
  }

  function formatWatchTime(value) {
    const totalSeconds = Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    const hours = Math.floor(minutes / 60)
    const remainingMinutes = minutes % 60
    return hours
      ? `${hours}:${String(remainingMinutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
      : `${minutes}:${String(seconds).padStart(2, '0')}`
  }

  function setWatchAction(action, payload = {}) {
    if (!canControlWatch) {
      setWatchError('Only the room owner or active controller can control the watch session.')
      return
    }
    const socket = watchSocketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setWatchError('Watch sync is not available right now.')
      return
    }
    socket.send(JSON.stringify({ action, ...payload }))
  }

  function applyWatchStateToPlayer(state) {
    const player = watchPlayerRef.current
    const youtubeApi = window.YT
    if (!watchPlayerReadyRef.current || !player || !youtubeApi?.PlayerState) return
    if (getYoutubeVideoId(state?.video_url) !== watchPlayerVideoIdRef.current) return

    const targetPosition = Number.isFinite(Number(state.position)) ? Math.max(0, Number(state.position)) : 0
    const currentPosition = player.getCurrentTime()
    if (Number.isFinite(currentPosition) && Math.abs(currentPosition - targetPosition) > 1.5) {
      player.seekTo(targetPosition, true)
    }

    const playerState = player.getPlayerState()
    if (state.is_playing) {
      if (playerState !== youtubeApi.PlayerState.PLAYING) player.playVideo()
    } else if (playerState !== youtubeApi.PlayerState.PAUSED && playerState !== youtubeApi.PlayerState.ENDED) {
      player.pauseVideo()
    }
  }

  function getWatchPosition() {
    if (watchPlayerReadyRef.current && watchPlayerRef.current) {
      return watchPlayerRef.current.getCurrentTime()
    }
    return Number(watchState?.position) || 0
  }

  function commitWatchSeek(position) {
    setWatchAction('seek', { position: Number(position) })
    setWatchSeekPosition(null)
  }

  async function loadRooms(offset = 0, append = false) {
    const page = await apiGetPage('/rooms/', offset)
    setRooms((current) => append ? [...current, ...page.data] : page.data)
    setRoomNextOffset(page.nextOffset)
    setHasMoreRooms(page.hasMore)
    if (!append && !page.data.some((room) => room.id === selectedRoomId && room.is_member)) {
      setSelectedRoomId(page.data.find((room) => room.is_member)?.id ?? null)
    }
  }

  async function loadMoreRooms() {
    if (isLoadingMoreRooms || !hasMoreRooms) return
    setIsLoadingMoreRooms(true)
    try {
      await loadRooms(roomNextOffset, true)
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsLoadingMoreRooms(false)
    }
  }

  useEffect(() => {
    loadRooms().catch((error) => setErrorMessage(error.message))
  }, [])

  useEffect(() => {
    let isCancelled = false
    let pollTimer
    let socket
    let socketIsOpen = false
    let hasLoadedHistory = false

    function schedulePoll() {
      if (!isCancelled && !socketIsOpen && hasLoadedHistory && !pollTimer) {
        pollTimer = window.setTimeout(pollMessages, MESSAGE_POLL_INTERVAL_MS)
      }
    }

    messagesRef.current = []
    setMessages([])
    setHasOlderMessages(false)
    previousScrollPositionRef.current = null
    if (!selectedRoomId) {
      setIsLoadingMessages(false)
      return undefined
    }

    setIsLoadingMessages(true)
    setErrorMessage('')

    async function pollMessages() {
      pollTimer = null
      if (socketIsOpen) return
      try {
        const lastMessage = messagesRef.current[messagesRef.current.length - 1]
        const after = lastMessage?.id ?? 0
        const newerMessages = await apiGet(`/rooms/${selectedRoomId}/messages/?after=${after}`)
        if (!isCancelled && newerMessages.length) {
          messagesRef.current = mergeMessages(messagesRef.current, newerMessages)
          setMessages(messagesRef.current)
        }
      } catch (error) {
        if (!isCancelled) setErrorMessage(error.message)
      } finally {
        schedulePoll()
      }
    }

    try {
      socket = new WebSocket(getWebSocketUrl(`/ws/chat/room/${selectedRoomId}/`))
      socket.onopen = () => {
        socketIsOpen = true
        window.clearTimeout(pollTimer)
        pollTimer = null
      }
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'message') {
            messagesRef.current = mergeMessages(messagesRef.current, [payload])
            setMessages(messagesRef.current)
          } else if (payload.type === 'error') {
            setErrorMessage(payload.message)
          }
        } catch (error) {
          setErrorMessage('The chat connection returned an unexpected message.')
        }
      }
      socket.onclose = () => {
        socketIsOpen = false
        schedulePoll()
      }
    } catch (error) {
      schedulePoll()
    }

    apiGet(`/rooms/${selectedRoomId}/messages/`)
      .then((initialMessages) => {
        if (isCancelled) return
        messagesRef.current = mergeMessages(initialMessages, messagesRef.current)
        setMessages(messagesRef.current)
        setHasOlderMessages(initialMessages.length === MESSAGE_HISTORY_PAGE_SIZE)
        hasLoadedHistory = true
        schedulePoll()
      })
      .catch((error) => {
        if (!isCancelled) setErrorMessage(error.message)
      })
      .finally(() => {
        if (!isCancelled) setIsLoadingMessages(false)
      })

    return () => {
      isCancelled = true
      window.clearTimeout(pollTimer)
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        socket.close()
      }
    }
  }, [selectedRoomId])

  useEffect(() => {
    const chatWindow = chatWindowRef.current
    if (!chatWindow) return
    if (previousScrollPositionRef.current) {
      const { height, top } = previousScrollPositionRef.current
      chatWindow.scrollTop = top + chatWindow.scrollHeight - height
      previousScrollPositionRef.current = null
      return
    }
    const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
    chatWindow.scrollTo({ top: chatWindow.scrollHeight, behavior })
  }, [messages])

  async function loadOlderMessages() {
    const firstMessage = messagesRef.current[0]
    if (!selectedRoomId || !firstMessage || isLoadingOlderMessages) return
    const chatWindow = chatWindowRef.current
    if (chatWindow) {
      previousScrollPositionRef.current = { height: chatWindow.scrollHeight, top: chatWindow.scrollTop }
    }
    setIsLoadingOlderMessages(true)
    try {
      const olderMessages = await apiGet(`/rooms/${selectedRoomId}/messages/?before=${firstMessage.id}`)
      const mergedMessages = mergeMessages(olderMessages, messagesRef.current)
      messagesRef.current = mergedMessages
      setMessages(mergedMessages)
      setHasOlderMessages(olderMessages.length === MESSAGE_HISTORY_PAGE_SIZE)
      if (!olderMessages.length) previousScrollPositionRef.current = null
    } catch (error) {
      previousScrollPositionRef.current = null
      setErrorMessage(error.message)
    } finally {
      setIsLoadingOlderMessages(false)
    }
  }

  async function handleCreateRoom(event) {
    event.preventDefault()
    if (!roomName.trim() || isCreatingRoom) return
    try {
      setIsCreatingRoom(true)
      setErrorMessage('')
      const room = await apiPost('/rooms/', { name: roomName.trim() })
      setRoomName('')
      setSelectedRoomId(room.id)
      setStatusMessage('Group room created.')
      await loadRooms()
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsCreatingRoom(false)
    }
  }

  async function handleLeaveRoom(room) {
    try {
      setErrorMessage('')
      await apiPost(`/rooms/${room.id}/leave/`, {})
      if (selectedRoomId === room.id) setSelectedRoomId(null)
      setStatusMessage(`Left ${room.name}.`)
      await loadRooms()
    } catch (error) {
      setErrorMessage(error.message)
    }
  }

  async function handleDeleteRoom(room) {
    if (!window.confirm(`Delete "${room.name}" and its messages?`)) return
    try {
      setErrorMessage('')
      await apiDelete(`/rooms/${room.id}/`)
      if (selectedRoomId === room.id) setSelectedRoomId(null)
      setStatusMessage(`${room.name} was deleted.`)
      await loadRooms()
    } catch (error) {
      setErrorMessage(error.message)
    }
  }

  async function openInviteDialog() {
    if (!selectedRoom) return
    setIsInviteOpen(true)
    setInviteLoading(true)
    setInviteError('')
    setInviteFeedback('')
    try {
      const [friendsPage, invitePage] = await Promise.all([
        apiGetPage('/friends/'),
        apiGetPage(`/rooms/${selectedRoom.id}/invitations/`),
      ])
      setInviteFriends(friendsPage.data)
      setInviteFriendNextOffset(friendsPage.nextOffset)
      setHasMoreInviteFriends(friendsPage.hasMore)
      setRoomMemberIds(invitePage.data.member_public_ids)
      setPendingInviteeIds(invitePage.data.invitations.map((invitation) => invitation.invitee.public_id))
    } catch (error) {
      setInviteError(error.message)
    } finally {
      setInviteLoading(false)
    }
  }

  async function loadMoreInviteFriends() {
    if (isLoadingMoreInviteFriends || !hasMoreInviteFriends) return
    setIsLoadingMoreInviteFriends(true)
    try {
      const page = await apiGetPage('/friends/', inviteFriendNextOffset)
      setInviteFriends((current) => [...current, ...page.data])
      setInviteFriendNextOffset(page.nextOffset)
      setHasMoreInviteFriends(page.hasMore)
    } catch (error) {
      setInviteError(error.message)
    } finally {
      setIsLoadingMoreInviteFriends(false)
    }
  }

  async function sendRoomInvite(friend) {
    if (sendingInviteId || pendingInviteeIds.includes(friend.public_id)) return
    setSendingInviteId(friend.public_id)
    setInviteError('')
    setInviteFeedback('')
    try {
      await apiPost(`/rooms/${selectedRoom.id}/invitations/`, { invitee_public_id: friend.public_id })
      setPendingInviteeIds((current) => [...current, friend.public_id])
      setInviteFeedback(`Invitation sent to ${friend.display_name || friend.username}.`)
    } catch (error) {
      setInviteError(error.message)
    } finally {
      setSendingInviteId('')
    }
  }

  async function handleSendMessage(event) {
    event.preventDefault()
    if (!selectedRoomId || !messageDraft.trim() || isSendingMessage) return
    try {
      setIsSendingMessage(true)
      setErrorMessage('')
      const message = await apiPost(`/rooms/${selectedRoomId}/messages/`, { content: messageDraft.trim() })
      messagesRef.current = mergeMessages(messagesRef.current, [message])
      setMessages(messagesRef.current)
      setMessageDraft('')
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsSendingMessage(false)
    }
  }

  useEffect(() => {
    watchStateRef.current = watchState
  }, [watchState])

  useEffect(() => {
    if (!youtubeVideoId) {
      watchPlayerReadyRef.current = false
      watchPlayerVideoIdRef.current = ''
      return undefined
    }

    let isCancelled = false
    loadYoutubeIframeApi()
      .then((youtubeApi) => {
        if (isCancelled || !watchPlayerContainerRef.current) return
        const player = new youtubeApi.Player(watchPlayerContainerRef.current, {
          height: '240',
          width: '100%',
          videoId: youtubeVideoId,
          playerVars: {
            controls: 0,
            modestbranding: 1,
            playsinline: 1,
            rel: 0,
          },
          events: {
            onReady: (event) => {
              if (isCancelled) {
                event.target.destroy()
                return
              }
              watchPlayerRef.current = event.target
              watchPlayerReadyRef.current = true
              watchPlayerVideoIdRef.current = youtubeVideoId
              const iframe = event.target.getIframe()
              iframe.style.width = '100%'
              iframe.style.height = '100%'
              applyWatchStateToPlayer(watchStateRef.current)
            },
            onError: () => setWatchError('YouTube could not play this video.'),
          },
        })
        watchPlayerRef.current = player
      })
      .catch((error) => {
        if (!isCancelled) setWatchError(error.message)
      })

    return () => {
      isCancelled = true
      const player = watchPlayerRef.current
      watchPlayerRef.current = null
      watchPlayerReadyRef.current = false
      watchPlayerVideoIdRef.current = ''
      player?.destroy()
    }
  }, [youtubeVideoId])

  useEffect(() => {
    applyWatchStateToPlayer(watchState)
  }, [watchState])

  useEffect(() => {
    if (!youtubeVideoId) {
      setWatchTimeline({ position: 0, duration: 0 })
      setWatchSeekPosition(null)
      return undefined
    }

    const timelineInterval = window.setInterval(() => {
      const player = watchPlayerRef.current
      if (!watchPlayerReadyRef.current || !player) return
      const position = player.getCurrentTime()
      const duration = player.getDuration()
      if (Number.isFinite(position) && Number.isFinite(duration)) {
        setWatchTimeline({ position, duration })
      }
    }, 500)

    return () => window.clearInterval(timelineInterval)
  }, [youtubeVideoId])

  useEffect(() => {
    if (!selectedRoomId || !watchSocketReady || !canControlWatch || !youtubeVideoId) return undefined

    const syncInterval = window.setInterval(() => {
      const socket = watchSocketRef.current
      const player = watchPlayerRef.current
      const youtubeApi = window.YT
      if (
        !socket || socket.readyState !== WebSocket.OPEN || !watchPlayerReadyRef.current
        || !player || !youtubeApi?.PlayerState
      ) return

      const playerState = player.getPlayerState()
      socket.send(JSON.stringify({
        action: 'sync',
        is_playing: playerState === youtubeApi.PlayerState.PLAYING,
        position: player.getCurrentTime(),
      }))
    }, 3000)

    return () => window.clearInterval(syncInterval)
  }, [selectedRoomId, watchSocketReady, canControlWatch, youtubeVideoId])

  useEffect(() => {
    if (!selectedRoomId) {
      setWatchState(null)
      setWatchVideoInput('')
      setWatchError('')
      setWatchSocketReady(false)
      return undefined
    }

    let isCancelled = false
    setWatchIsLoading(true)
    setWatchError('')
    setWatchState(null)

    async function loadWatchState() {
      try {
        const session = await apiGet(`/rooms/${selectedRoomId}/watch/`)
        if (isCancelled) return
        setWatchState(session)
        setWatchVideoInput(session.video_url || '')
      } catch (error) {
        if (!isCancelled) setWatchError(error.message)
      } finally {
        if (!isCancelled) setWatchIsLoading(false)
      }
    }

    const socket = new WebSocket(getWatchSocketUrl(selectedRoomId))
    watchSocketRef.current = socket

    socket.onopen = () => {
      if (!isCancelled) setWatchSocketReady(true)
    }

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (!isCancelled && (payload.type === 'state' || payload.type === 'watch_state')) {
          setWatchState(payload.state)
          setWatchVideoInput(payload.state.video_url || '')
        } else if (!isCancelled && payload.type === 'error') {
          setWatchError(payload.message)
        }
      } catch (error) {
        if (!isCancelled) setWatchError('The watch session returned an unexpected message.')
      }
    }

    socket.onerror = () => {
      if (!isCancelled) setWatchError('Room watch connection failed.')
    }

    socket.onclose = () => {
      if (!isCancelled) setWatchSocketReady(false)
    }

    loadWatchState()

    return () => {
      isCancelled = true
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close()
      }
      watchSocketRef.current = null
      setWatchSocketReady(false)
    }
  }, [selectedRoomId])

  async function handleWatchSubmit(event) {
    event.preventDefault()
    if (!canControlWatch) {
      setWatchError('Only the room owner or active controller can control the watch session.')
      return
    }
    const trimmedUrl = watchVideoInput.trim()
    if (!trimmedUrl || !selectedRoomId) return
    setWatchError('')
    const socket = watchSocketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setWatchError('The watch sync connection is not ready yet.')
      return
    }
    socket.send(JSON.stringify({ action: 'set_video', video_url: trimmedUrl }))
  }

  const visibleFriends = inviteFriends.filter((friend) => {
    const name = friend.display_name || friend.username
    return !roomMemberIds.includes(friend.public_id) && name.toLowerCase().includes(inviteSearch.trim().toLowerCase())
  })

  return (
    <div className="rooms-page rooms-workspace">
      <aside className="rooms-side-panel rooms-list-panel" aria-labelledby="rooms-heading">
        <div className="rooms-side-heading">
          <p className="rooms-kicker">YOUR SPACE</p>
          <h1 id="rooms-heading">Group rooms</h1>
        </div>
        <ul className="room-list is-open">
          {rooms.length === 0 ? <li className="room-empty">No rooms yet. Create one to get started.</li> : rooms.map((room) => (
            <li key={room.id} className={`${selectedRoomId === room.id ? 'selected-room' : ''} ${!room.is_member ? 'room-not-member' : ''}`}>
              <span className="room-status" aria-hidden="true" />
              <button className="room-select-button" type="button" disabled={!room.is_member} onClick={() => setSelectedRoomId(room.id)}>
                <strong>{room.name}</strong>
                <small>{room.member_count} {room.member_count === 1 ? 'member' : 'members'}</small>
              </button>
              {room.is_owner ? (
                <button type="button" className="room-link-button danger" onClick={() => handleDeleteRoom(room)}>Delete</button>
              ) : room.is_member ? (
                <button type="button" className="room-link-button" onClick={() => handleLeaveRoom(room)}>Leave</button>
              ) : null}
            </li>
          ))}
        </ul>
        {hasMoreRooms && <button type="button" className="button button-yellow" onClick={loadMoreRooms} disabled={isLoadingMoreRooms}>{isLoadingMoreRooms ? 'Loading...' : 'Load more rooms'}</button>}

        <div className="room-create-section">
          <div className="rooms-side-heading">
            <p className="rooms-kicker">MAKE IT A MOMENT</p>
            <h2 id="room-create-heading">Create a room</h2>
          </div>
          <form className="room-create-form" onSubmit={handleCreateRoom}>
            <label htmlFor="room-name">Room name</label>
            <input id="room-name" value={roomName} onChange={(event) => setRoomName(event.target.value)} maxLength="80" placeholder="e.g. Friday night" required />
            <button className="button button-yellow" type="submit" disabled={isCreatingRoom}>{isCreatingRoom ? 'Creating...' : 'Create room'}</button>
          </form>
        </div>

        {selectedRoom && (
          <div className="room-sidebar-details">
            <p className="rooms-kicker">CURRENT ROOM</p>
            <strong>{selectedRoom.member_count} {selectedRoom.member_count === 1 ? 'member' : 'members'}</strong>
            <button type="button" className="button button-yellow" onClick={openInviteDialog}>Invite friends</button>
          </div>
        )}

        {(errorMessage || statusMessage) && <div className={`room-feedback ${errorMessage ? 'error-text' : ''}`} role={errorMessage ? 'alert' : 'status'}>{errorMessage || statusMessage}</div>}
      </aside>

      <section className="room-chat-workspace" aria-labelledby="room-chat-heading">
        <header className="room-chat-header">
          <div className="room-chat-title">
            <p className="rooms-kicker">GROUP CHAT</p>
            <h2 id="room-chat-heading">{selectedRoom?.name || 'Choose a room'}</h2>
          </div>
        </header>
        {selectedRoom ? (
          <>
            <div className="chat-window" ref={chatWindowRef} aria-live="polite" aria-busy={isLoadingMessages}>
              {hasOlderMessages && <button type="button" className="button button-yellow" onClick={loadOlderMessages} disabled={isLoadingOlderMessages}>{isLoadingOlderMessages ? 'Loading earlier messages...' : 'Load earlier messages'}</button>}
              {isLoadingMessages ? <p className="muted" role="status">Loading chat...</p> : messages.length === 0 ? <p className="muted chat-empty-prompt">Say hello to the group.</p> : messages.map((message) => {
                const isOwnMessage = message.sender?.public_id === user.public_id
                return <div key={message.id} className={`chat-message ${isOwnMessage ? 'mine' : ''}`}><div className="chat-message-author"><UserAvatar profile={isOwnMessage ? profile : message.sender} /><strong>{isOwnMessage ? 'You' : (message.sender?.display_name || message.sender?.username)}</strong></div><p>{message.content}</p></div>
              })}
            </div>
            <form onSubmit={handleSendMessage} className="message-form">
              <label className="sr-only" htmlFor="room-message">Message the group</label>
              <input id="room-message" value={messageDraft} onChange={(event) => setMessageDraft(event.target.value)} placeholder="Send a message to the group" />
              <button type="submit" className="button button-pink" disabled={isSendingMessage}>{isSendingMessage ? 'Sending...' : 'Send'}</button>
            </form>
          </>
        ) : (
          <div className="room-chat-empty">
            <span className="room-empty-mark" aria-hidden="true">✦</span>
            <p>Pick a room and join the conversation.</p>
          </div>
        )}
      </section>

      <section className="room-watch-panel" aria-labelledby="room-watch-heading">
        <div className="room-watch-header">
          <div>
            <p className="rooms-kicker">SYNC WATCH</p>
            <h3 id="room-watch-heading">Room watch</h3>
          </div>
        </div>

        {!selectedRoom ? (
          <p className="muted">Select a room to start the watch party.</p>
        ) : watchIsLoading ? (
          <p className="muted" role="status">Loading the room watch session...</p>
        ) : (
          <>
            {youtubeVideoId ? (
              <div className="watch-video-shell">
                <div className="watch-video-frame" role="group" aria-label="Shared YouTube video">
                  <div className="watch-video-target" ref={watchPlayerContainerRef} />
                </div>
              </div>
            ) : (
              <div className="watch-empty-state">
                <div className="watch-empty-icon" aria-hidden="true">▶</div>
                <p>Paste a YouTube link to start a shared watch session.</p>
              </div>
            )}

            <div className="watch-controls-row">
              <button type="button" className="mini-button" onClick={() => setWatchAction('play')} disabled={!watchSocketReady || !canControlWatch}>Play</button>
              <button type="button" className="mini-button" onClick={() => setWatchAction('pause')} disabled={!watchSocketReady || !canControlWatch}>Pause</button>
              <button type="button" className="mini-button" onClick={() => setWatchAction('seek', { position: getWatchPosition() + 10 })} disabled={!watchSocketReady || !canControlWatch}>+10s</button>
            </div>

            {youtubeVideoId && (
              <div className="watch-seek-control">
                <label className="sr-only" htmlFor="watch-video-position">Seek shared video</label>
                <input
                  id="watch-video-position"
                  type="range"
                  min="0"
                  max={watchTimeline.duration || 0}
                  step="1"
                  value={watchSeekPosition ?? Math.min(watchTimeline.position, watchTimeline.duration || 0)}
                  onChange={(event) => setWatchSeekPosition(event.target.value)}
                  onPointerUp={(event) => commitWatchSeek(event.currentTarget.value)}
                  onKeyUp={(event) => commitWatchSeek(event.currentTarget.value)}
                  disabled={!watchSocketReady || !canControlWatch || !watchTimeline.duration}
                />
                <span aria-live="off">{formatWatchTime(watchSeekPosition ?? watchTimeline.position)}</span>
                <span>{formatWatchTime(watchTimeline.duration)}</span>
              </div>
            )}

            <form className="watch-form" onSubmit={handleWatchSubmit}>
              <label className="sr-only" htmlFor="watch-video-url">YouTube video URL</label>
              <input id="watch-video-url" value={watchVideoInput} onChange={(event) => setWatchVideoInput(event.target.value)} placeholder="https://www.youtube.com/watch?v=..." disabled={!canControlWatch} />
              <button type="submit" className="button button-yellow" disabled={!watchSocketReady || !canControlWatch}>Set video</button>
            </form>

            <div className="watch-meta">
              <span className="watch-controller">{watchState?.controller && <UserAvatar profile={watchState.controller} />}<span>{watchState?.controller ? `Controller: ${watchState.controller.display_name || watchState.controller.username}` : 'Controller: nobody yet'}</span></span>
              <span>{watchState ? `${formatWatchTime(watchTimeline.duration ? watchTimeline.position : watchState.position || 0)} • ${watchState.is_playing ? 'Playing' : 'Paused'}` : 'Awaiting session'}</span>
            </div>
          </>
        )}

        {watchError && <p className="room-feedback error-text" role="alert">{watchError}</p>}
      </section>

      {isInviteOpen && selectedRoom && (
        <div className="invite-backdrop" onClick={() => setIsInviteOpen(false)}>
          <section className="invite-dialog" role="dialog" aria-modal="true" aria-labelledby="invite-heading" onClick={(event) => event.stopPropagation()}>
            <div className="invite-dialog-heading">
              <div>
                <p className="card-label">ROOM INVITATION</p>
                <h2 id="invite-heading">Invite to {selectedRoom.name}</h2>
              </div>
              <button type="button" className="invite-close" aria-label="Close invite dialog" onClick={() => setIsInviteOpen(false)}>×</button>
            </div>
            <label className="sr-only" htmlFor="invite-search">Search friends</label>
            <input id="invite-search" className="invite-search" value={inviteSearch} onChange={(event) => setInviteSearch(event.target.value)} placeholder="Search friends" />
            {inviteLoading ? <p className="muted" role="status">Loading friends...</p> : (
              <ul className="invite-friend-list">
                {visibleFriends.map((friend) => {
                  const isPending = pendingInviteeIds.includes(friend.public_id)
                  return (
                    <li key={friend.public_id}>
                      <span className="user-identity"><UserAvatar profile={friend} /><span>{friend.display_name || friend.username}</span></span>
                      <button type="button" className="mini-button success" disabled={isPending || Boolean(sendingInviteId)} onClick={() => sendRoomInvite(friend)}>
                        {isPending ? 'Invited' : sendingInviteId === friend.public_id ? 'Sending...' : 'Invite'}
                      </button>
                    </li>
                  )
                })}
                {!visibleFriends.length && <li className="invite-empty">No friends available to invite.</li>}
              </ul>
            )}
            {!inviteLoading && hasMoreInviteFriends && <button type="button" className="button button-yellow" onClick={loadMoreInviteFriends} disabled={isLoadingMoreInviteFriends}>{isLoadingMoreInviteFriends ? 'Loading...' : 'Load more friends'}</button>}
            {inviteError && <p className="room-feedback error-text" role="alert">{inviteError}</p>}
            {inviteFeedback && <p className="room-feedback" role="status">{inviteFeedback}</p>}
          </section>
        </div>
      )}
    </div>
  )
}

export default GroupRooms