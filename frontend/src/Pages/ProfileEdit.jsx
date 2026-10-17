import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getMediaUrl } from '../api/client'
import { useAuth } from '../auth/useAuth'

function ProfileEdit() {
  const { profile, profileError, isLoading, updateProfile } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', display_name: '', bio: '' })
  const [avatarFile, setAvatarFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [error, setError] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  function hasChanges() {
    if (!profile) return false
    return Boolean(avatarFile) || form.username !== (profile.username || '') || form.display_name !== (profile.display_name || '') || form.bio !== (profile.bio || '')
  }

  useEffect(() => {
    if (!profile) return
    setForm({
      username: profile.username || '',
      display_name: profile.display_name || '',
      bio: profile.bio || '',
    })
  }, [profile])

  useEffect(() => {
    if (!avatarFile) return undefined
    const objectUrl = URL.createObjectURL(avatarFile)
    setPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [avatarFile])

  useEffect(() => {
    function handleBeforeUnload(event) {
      if (hasChanges()) {
        event.preventDefault()
        event.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  })

  function updateField(event) {
    setForm({ ...form, [event.target.name]: event.target.value })
  }

  function handleAvatarChange(event) {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Please choose an image file.')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('Profile pictures must be 5 MB or smaller.')
      return
    }
    setError('')
    setAvatarFile(file)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setIsSaving(true)
    const formData = new FormData()
    formData.append('username', form.username.trim())
    formData.append('display_name', form.display_name.trim())
    formData.append('bio', form.bio.trim())
    if (avatarFile) formData.append('avatar', avatarFile)

    try {
      await updateProfile(formData)
      navigate('/profile', { state: { saved: true } })
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return <main className="profile-page"><p className="profile-status">Loading your profile...</p></main>
  }

  if (profileError || !profile) {
    return (
      <main className="profile-page">
        <section className="profile-status profile-status-error" role="alert">
          <h1>We could not open the profile editor.</h1>
          <p>{profileError || 'Your profile is not available yet.'}</p>
          <Link className="button button-yellow" to="/profile">Back to profile</Link>
        </section>
      </main>
    )
  }

  const preview = previewUrl || getMediaUrl(profile.avatar, profile.updated_at)
  const avatarInitial = (form.display_name || form.username || '?').charAt(0).toUpperCase()

  return (
    <main className="profile-page">
      <section className="profile-editor" aria-labelledby="profile-edit-heading">
        <div className="profile-editor-heading">
          <div>
            <p className="eyebrow">MAKE IT YOURS</p>
            <h1 id="profile-edit-heading">Edit profile</h1>
          </div>
          <Link className="profile-cancel" to="/profile">Cancel</Link>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="profile-picture-editor">
            {preview ? <img className="profile-large-avatar" src={preview} alt="Profile preview" /> : <span className="profile-large-avatar profile-avatar-fallback" aria-hidden="true">{avatarInitial}</span>}
            <label className="upload-button" htmlFor="avatar">Change picture</label>
            <input id="avatar" type="file" accept="image/*" onChange={handleAvatarChange} />
              <p>JPG or PNG up to 5 MB.</p>
          </div>

          <div className="profile-form-fields">
            <label htmlFor="username">Username</label>
            <input id="username" name="username" value={form.username} onChange={updateField} maxLength="150" required />

            <label htmlFor="display_name">Display name</label>
            <input id="display_name" name="display_name" value={form.display_name} onChange={updateField} maxLength="80" placeholder="What should friends call you?" />

            <label htmlFor="bio">About you</label>
            <textarea id="bio" name="bio" value={form.bio} onChange={updateField} maxLength="240" rows="4" placeholder="A little line about you..." />
            <span className="character-count">{form.bio.length}/240</span>
          </div>

          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit" disabled={isSaving}>{isSaving ? 'Saving...' : 'Save profile'}</button>
        </form>
      </section>
    </main>
  )
}

export default ProfileEdit
