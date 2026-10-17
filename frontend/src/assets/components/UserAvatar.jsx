import { getMediaUrl } from '../../api/client'

function UserAvatar({ profile, size = 'small' }) {
  const name = profile?.display_name || profile?.username || '?'
  const avatarUrl = getMediaUrl(profile?.avatar)

  return (
    <span className={`user-avatar user-avatar-${size}`} aria-hidden="true">
      <span>{name.charAt(0).toUpperCase()}</span>
      {avatarUrl && <img src={avatarUrl} alt="" onError={(event) => event.currentTarget.remove()} />}
    </span>
  )
}

export default UserAvatar