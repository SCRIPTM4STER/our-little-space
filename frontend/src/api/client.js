const configuredApiUrl = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')
const isLocalApiUrl = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/api)?$/i.test(configuredApiUrl)
const useViteProxy = import.meta.env.DEV && isLocalApiUrl
const apiOrigin = useViteProxy ? window.location.origin : configuredApiUrl
const API_BASE_URL = apiOrigin.endsWith('/api') ? apiOrigin : `${apiOrigin}/api`

export function getMediaUrl(path, version) {
  if (!path) return null
  const apiOrigin = new URL(API_BASE_URL, window.location.origin).origin
  const mediaUrl = new URL(path, `${apiOrigin}/`)
  if (version) mediaUrl.searchParams.set('v', version)
  return mediaUrl.href
}

export function getWebSocketUrl(path) {
  const websocketBase = apiOrigin.endsWith('/api') ? apiOrigin.slice(0, -4) : apiOrigin
  const websocketUrl = websocketBase.replace(/^http/, 'ws')
  const token = localStorage.getItem('auth_token')
  return `${websocketUrl}${path}?token=${encodeURIComponent(token || '')}`
}

export async function apiRequest(path, options = {}, includePageInfo = false) {
  const token = localStorage.getItem('auth_token')
  const headers = new Headers(options.headers || {})
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData

  if (options.body != null && !isFormData) headers.set('Content-Type', 'application/json')
  if (token) {
    headers.set('Authorization', `Token ${token}`)
  }

  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    })
  } catch (error) {
    throw new Error(
      `Unable to connect to the backend at ${API_BASE_URL}. Check that Django is running and that this frontend origin is allowed by CORS.`,
      { cause: error },
    )
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && token) {
      window.dispatchEvent(new Event('authentication-expired'))
    }
    const message = getErrorMessage(payload) || `Request failed (${response.status})`
    const error = new Error(message)
    error.status = response.status
    error.data = payload
    throw error
  }

  const data = payload?.data ?? payload
  if (!includePageInfo) return data
  return {
    data,
    nextOffset: Number(response.headers.get('X-Next-Offset') || 0),
    hasMore: response.headers.get('X-Has-More') === 'true',
  }
}

export const apiGet = (path, options = {}) => apiRequest(path, {
  ...options,
  method: 'GET',
})

export const apiGetPage = (path, offset = 0) => {
  const separator = path.includes('?') ? '&' : '?'
  return apiRequest(`${path}${separator}offset=${offset}`, { method: 'GET' }, true)
}

export const apiPost = (path, body, options = {}) => apiRequest(path, {
  ...options,
  method: 'POST',
  body: body instanceof FormData ? body : JSON.stringify(body),
})

export const apiPatch = (path, body, options = {}) => apiRequest(path, {
  ...options,
  method: 'PATCH',
  body: body instanceof FormData ? body : JSON.stringify(body),
})

export const apiDelete = (path, options = {}) => apiRequest(path, {
  ...options,
  method: 'DELETE',
})

function getErrorMessage(payload) {
  if (!payload) return null
  if (typeof payload === 'string') return payload
  if (payload.detail) return payload.detail
  if (payload.data?.detail) return payload.data.detail

  const firstError = Object.values(payload)[0]
  if (Array.isArray(firstError)) return firstError[0]
  if (typeof firstError === 'string') return firstError
  return null
}
