import { useEffect, useRef, useState } from 'react'
import { apiGet, apiGetPage, apiPost, getWebSocketUrl } from '../api/client'
import { useAuth } from '../auth/useAuth'
import UserAvatar from '../assets/components/UserAvatar'
import { mergeMessages, MESSAGE_HISTORY_PAGE_SIZE, MESSAGE_POLL_INTERVAL_MS } from '../utils/messages'

function Messages() {
  const { user, profile } = useAuth()
  const [friends, setFriends] = useState([])
  const [conversations, setConversations] = useState([])
  const [friendNextOffset, setFriendNextOffset] = useState(0)
  const [conversationNextOffset, setConversationNextOffset] = useState(0)
  const [hasMoreFriends, setHasMoreFriends] = useState(false)
  const [hasMoreConversations, setHasMoreConversations] = useState(false)
  const [isLoadingMoreFriends, setIsLoadingMoreFriends] = useState(false)
  const [isLoadingMoreConversations, setIsLoadingMoreConversations] = useState(false)
  const [selectedConversationId, setSelectedConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isLoadingOlderMessages, setIsLoadingOlderMessages] = useState(false)
  const [hasOlderMessages, setHasOlderMessages] = useState(false)
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [messageDraft, setMessageDraft] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const messagesRef = useRef([])
  const chatWindowRef = useRef(null)
  const previousScrollPositionRef = useRef(null)

  async function loadMessagesData() {
    const [friendsPage, conversationsPage] = await Promise.all([apiGetPage('/friends/'), apiGetPage('/conversations/')])
    setFriends(friendsPage.data)
    setConversations(conversationsPage.data)
    setFriendNextOffset(friendsPage.nextOffset)
    setConversationNextOffset(conversationsPage.nextOffset)
    setHasMoreFriends(friendsPage.hasMore)
    setHasMoreConversations(conversationsPage.hasMore)
    if (!selectedConversationId && conversationsPage.data.length) setSelectedConversationId(conversationsPage.data[0].id)
  }

  async function loadMoreFriends() {
    if (isLoadingMoreFriends || !hasMoreFriends) return
    setIsLoadingMoreFriends(true)
    try {
      const page = await apiGetPage('/friends/', friendNextOffset)
      setFriends((current) => [...current, ...page.data])
      setFriendNextOffset(page.nextOffset)
      setHasMoreFriends(page.hasMore)
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsLoadingMoreFriends(false)
    }
  }

  async function loadMoreConversations() {
    if (isLoadingMoreConversations || !hasMoreConversations) return
    setIsLoadingMoreConversations(true)
    try {
      const page = await apiGetPage('/conversations/', conversationNextOffset)
      setConversations((current) => [...current, ...page.data])
      setConversationNextOffset(page.nextOffset)
      setHasMoreConversations(page.hasMore)
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsLoadingMoreConversations(false)
    }
  }

  useEffect(() => {
    loadMessagesData().catch((error) => setErrorMessage(error.message))
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
    if (!selectedConversationId) {
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
        const newerMessages = await apiGet(`/conversations/${selectedConversationId}/messages/?after=${after}`)
        if (!isCancelled && newerMessages.length) {
          messagesRef.current = mergeMessages(messagesRef.current, newerMessages)
          setMessages(messagesRef.current)
          const latestMessage = messagesRef.current[messagesRef.current.length - 1]
          setConversations((current) => current.map((conversation) => (
            conversation.id === selectedConversationId
              ? { ...conversation, last_message: latestMessage }
              : conversation
          )))
          window.dispatchEvent(new Event('activity-updated'))
        }
      } catch (error) {
        if (!isCancelled) setErrorMessage(error.message)
      } finally {
        schedulePoll()
      }
    }

    async function loadInitialMessages() {
      try {
        const initialMessages = await apiGet(`/conversations/${selectedConversationId}/messages/`)
        if (isCancelled) return
        messagesRef.current = mergeMessages(initialMessages, messagesRef.current)
        setMessages(messagesRef.current)
        setHasOlderMessages(initialMessages.length === MESSAGE_HISTORY_PAGE_SIZE)
        window.dispatchEvent(new Event('activity-updated'))
        hasLoadedHistory = true
        schedulePoll()
      } catch (error) {
        if (!isCancelled) {
          setErrorMessage(error.message)
          pollTimer = window.setTimeout(loadInitialMessages, MESSAGE_POLL_INTERVAL_MS)
        }
      } finally {
        if (!isCancelled) setIsLoadingMessages(false)
      }
    }

    try {
      socket = new WebSocket(getWebSocketUrl(`/ws/chat/direct/${selectedConversationId}/`))
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
            const latestMessage = messagesRef.current[messagesRef.current.length - 1]
            setConversations((current) => current.map((conversation) => (
              conversation.id === selectedConversationId
                ? { ...conversation, last_message: latestMessage }
                : conversation
            )))
            window.dispatchEvent(new Event('activity-updated'))
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

    loadInitialMessages()

    return () => {
      isCancelled = true
      window.clearTimeout(pollTimer)
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        socket.close()
      }
    }
  }, [selectedConversationId])

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
    if (!selectedConversationId || !firstMessage || isLoadingOlderMessages) return
    const chatWindow = chatWindowRef.current
    if (chatWindow) {
      previousScrollPositionRef.current = { height: chatWindow.scrollHeight, top: chatWindow.scrollTop }
    }
    setIsLoadingOlderMessages(true)
    try {
      const olderMessages = await apiGet(`/conversations/${selectedConversationId}/messages/?before=${firstMessage.id}`)
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

  async function startConversation(publicId) {
    try {
      setErrorMessage('')
      const conversation = await apiPost('/conversations/', { participant_public_id: publicId })
      setSelectedConversationId(conversation.id)
      await loadMessagesData()
    } catch (error) {
      setErrorMessage(error.message)
    }
  }

  async function sendMessage(event) {
    event.preventDefault()
    if (!selectedConversationId || !messageDraft.trim() || isSendingMessage) return
    try {
      setIsSendingMessage(true)
      setErrorMessage('')
      const message = await apiPost(`/conversations/${selectedConversationId}/messages/`, { content: messageDraft.trim() })
      messagesRef.current = mergeMessages(messagesRef.current, [message])
      setMessages(messagesRef.current)
      setConversations((current) => current.map((conversation) => (
        conversation.id === selectedConversationId
          ? { ...conversation, last_message: message }
          : conversation
      )))
      setMessageDraft('')
      await loadMessagesData()
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsSendingMessage(false)
    }
  }

  const selectedConversation = conversations.find((conversation) => conversation.id === selectedConversationId)

  return (
    <div className="rooms-page">
      <section className="rooms-intro">
        <p className="eyebrow">ONE-TO-ONE CONVERSATIONS</p>
        <h1>Direct messages.</h1>
        <p>Your private conversations with friends, separate from group rooms.</p>
      </section>
      <section className="social-grid messages-grid">
        <div className="social-card text-black">
          <h3>Friends</h3>
          {friends.length === 0 ? <p className="muted">Add friends to start a private conversation.</p> : (
            <ul className="social-list">
              {friends.map((friend) => <li key={friend.public_id}><div className="user-identity"><UserAvatar profile={friend} /><span>{friend.display_name || friend.username}</span></div><button type="button" className="mini-button success" onClick={() => startConversation(friend.public_id)}>Message</button></li>)}
            </ul>
          )}
          {hasMoreFriends && <button type="button" className="button button-yellow" onClick={loadMoreFriends} disabled={isLoadingMoreFriends}>{isLoadingMoreFriends ? 'Loading...' : 'Load more friends'}</button>}
        </div>
        <div className="social-card text-black">
          <h3>Conversations</h3>
          <div className="conversation-list">
            {conversations.length === 0 ? <p className="muted">No conversations yet.</p> : conversations.map((conversation) => (
              <button type="button" key={conversation.id} className={`conversation-item${selectedConversationId === conversation.id ? ' selected' : ''}`} onClick={() => setSelectedConversationId(conversation.id)}>
                <span className="conversation-person"><UserAvatar profile={conversation.other_user} /><span>{conversation.other_user?.display_name || conversation.other_user?.username}</span></span>
                <small>{conversation.last_message?.content || 'No messages yet'}</small>
              </button>
            ))}
          </div>
          {hasMoreConversations && <button type="button" className="button button-yellow" onClick={loadMoreConversations} disabled={isLoadingMoreConversations}>{isLoadingMoreConversations ? 'Loading...' : 'Load more conversations'}</button>}
          {selectedConversation && (
            <div className="chat-panel">
              <h4 className="chat-contact-heading"><UserAvatar profile={selectedConversation.other_user} size="medium" /><span>{selectedConversation.other_user?.display_name || selectedConversation.other_user?.username}</span></h4>
              <div className="chat-window" ref={chatWindowRef} aria-live="polite" aria-busy={isLoadingMessages}>
                {hasOlderMessages && <button type="button" className="button button-yellow" onClick={loadOlderMessages} disabled={isLoadingOlderMessages}>{isLoadingOlderMessages ? 'Loading earlier messages...' : 'Load earlier messages'}</button>}
                {isLoadingMessages ? <p className="muted" role="status">Loading conversation...</p> : messages.length === 0 ? <p className="muted">Start the conversation.</p> : messages.map((message) => {
                  const isOwnMessage = message.sender?.public_id === user.public_id
                  return <div key={message.id} className={`chat-message ${isOwnMessage ? 'mine' : ''}`}><div className="chat-message-author"><UserAvatar profile={isOwnMessage ? profile : message.sender} /><strong>{isOwnMessage ? 'You' : (message.sender?.display_name || message.sender?.username)}</strong></div><p>{message.content}</p></div>
                })}
              </div>
              <form onSubmit={sendMessage} className="message-form">
                <label className="sr-only" htmlFor="direct-message">Direct message</label>
                <input id="direct-message" value={messageDraft} onChange={(event) => setMessageDraft(event.target.value)} placeholder="Send a private message" />
                <button type="submit" className="button button-pink" disabled={isSendingMessage}>{isSendingMessage ? 'Sending...' : 'Send'}</button>
              </form>
            </div>
          )}
        </div>
      </section>
      {errorMessage && <div className="room-feedback error-text" role="alert">{errorMessage}</div>}
    </div>
  )
}

export default Messages