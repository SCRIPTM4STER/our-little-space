import { Link, useLocation } from 'react-router-dom'
import { getMediaUrl } from '../api/client'
import { useAuth } from '../auth/useAuth'

function Profile() {
  const { user, profile, profileError, isLoading, logout } = useAuth()
  const location = useLocation()
  const accountName = profile?.display_name || profile?.username || user?.username || 'Our Little Space user'
  const avatarInitial = accountName.charAt(0).toUpperCase()
  const savedMessage = location.state?.saved

  if (isLoading) {
    return <main className="profile-page"><p className="profile-status">Loading your profile...</p></main>
  }

  if (profileError) {
    return (
      <main className="profile-page">
        <section className="profile-status profile-status-error" role="alert">
          <h1>We could not load your profile.</h1>
          <p>{profileError}</p>
          <Link className="button button-yellow" to="/">Back home</Link>
        </section>
      </main>
    )
  }

  if (!profile) {
    return (
      <main className="profile-page">
        <section className="profile-status">
          <h1>Your profile is ready to make yours.</h1>
          <Link className="button button-yellow" to="/profile/edit">Set up profile</Link>
        </section>
      </main>
    )
  }

  return (
    <main className="profile-page">
      <section className="profile-card" aria-labelledby="profile-heading">
        {savedMessage && <p className="profile-success" role="status">Profile saved.</p>}
        <div className="profile-card-header">
          {profile.avatar ? (
            <img className="profile-large-avatar" src={getMediaUrl(profile.avatar, profile.updated_at)} alt="" />
          ) : (
            <span className="profile-large-avatar profile-avatar-fallback" aria-hidden="true">{avatarInitial}</span>
          )}
          <div>
            <p className="eyebrow">YOUR LITTLE CORNER</p>
            <h1 id="profile-heading">{accountName}</h1>
            <p className="profile-username">@{profile.username}</p>
          </div>
        </div>

        <div className="profile-details">
          <div>
            <span className="profile-detail-label">About</span>
            <p>{profile.bio || 'No bio yet. Add a little something about yourself.'}</p>
          </div>
          <div>
            <span className="profile-detail-label">Email</span>
            <p>{user?.email || 'No email added'}</p>
          </div>
        </div>

        <div className="profile-actions">
          <Link className="button button-yellow" to="/profile/edit">Edit profile</Link>
          <button className="profile-logout" type="button" onClick={logout}>Log out</button>
        </div>
      </section>
    </main>
  )
}

export default Profile
