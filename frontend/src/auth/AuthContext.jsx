import { useEffect, useState } from 'react'
import { apiGet, apiPatch, apiPost } from '../api/client'
import { AuthContext } from './context'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [profileError, setProfileError] = useState('')
  const [isLoading, setIsLoading] = useState(() => Boolean(localStorage.getItem('auth_token')))

  useEffect(() => {
    function clearExpiredAuthentication() {
      localStorage.removeItem('auth_token')
      setUser(null)
      setProfile(null)
      setProfileError('')
    }
    window.addEventListener('authentication-expired', clearExpiredAuthentication)
    return () => window.removeEventListener('authentication-expired', clearExpiredAuthentication)
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (!token) return

    apiGet('/auth/me/')
      .then((currentUser) => {
        setUser(currentUser)
        return apiGet('/profile/').catch((error) => {
          setProfileError(error.message)
          return null
        })
      })
      .then(setProfile)
      .catch(() => {
        localStorage.removeItem('auth_token')
        setUser(null)
        setProfile(null)
      })
      .finally(() => setIsLoading(false))
  }, [])

  async function login(credentials) {
    const data = await apiPost('/auth/login/', credentials)
    localStorage.setItem('auth_token', data.token)
    setUser(data.user)
    setProfileError('')
    setProfile(await apiGet('/profile/'))
    return data.user
  }

  async function register(credentials) {
    const data = await apiPost('/auth/register/', credentials)
    localStorage.setItem('auth_token', data.token)
    setUser(data.user)
    setProfileError('')
    setProfile(await apiGet('/profile/'))
    return data.user
  }

  async function logout() {
    try {
      await apiPost('/auth/logout/', {})
    } finally {
      localStorage.removeItem('auth_token')
      setUser(null)
      setProfile(null)
      setProfileError('')
    }
  }

  async function updateProfile(formData) {
    const updatedProfile = await apiPatch('/profile/', formData)
    setProfile(updatedProfile)
    setProfileError('')
    setUser((currentUser) => currentUser ? { ...currentUser, username: updatedProfile.username } : currentUser)
    return updatedProfile
  }

  return (
    <AuthContext.Provider value={{ user, profile, profileError, isLoading, login, register, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  )
}
