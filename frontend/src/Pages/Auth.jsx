import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

function Auth({ mode }) {
  const isLogin = mode === 'login'
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    password_confirmation: '',
  })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function updateField(event) {
    setForm({ ...form, [event.target.name]: event.target.value })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      if (isLogin) {
        await login({ username: form.username, password: form.password })
      } else {
        await register(form)
      }
      navigate(location.state?.from || '/rooms')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-heading">
        <p className="eyebrow">OUR LITTLE SPACE</p>
        <h1 id="auth-heading">{isLogin ? 'Welcome back.' : 'Come hang out.'}</h1>
        <p className="auth-intro">
          {isLogin ? 'Sign in to pick up where you left off.' : 'Create an account for your rooms and conversations.'}
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="username">Username</label>
          <input id="username" name="username" value={form.username} onChange={updateField} required autoComplete="username" />

          {!isLogin && (
            <>
              <label htmlFor="email">Email <span>(optional)</span></label>
              <input id="email" name="email" type="email" value={form.email} onChange={updateField} autoComplete="email" />
            </>
          )}

          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" value={form.password} onChange={updateField} required minLength="8" autoComplete={isLogin ? 'current-password' : 'new-password'} />

          {!isLogin && (
            <>
              <label htmlFor="password_confirmation">Confirm password</label>
              <input id="password_confirmation" name="password_confirmation" type="password" value={form.password_confirmation} onChange={updateField} required minLength="8" autoComplete="new-password" />
            </>
          )}

          {error && <p className="auth-error" role="alert">{error}</p>}

          <button className="auth-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'One moment...' : isLogin ? 'Log in' : 'Create account'}
          </button>
        </form>

        <p className="auth-switch">
          {isLogin ? 'Need an account? ' : 'Already have an account? '}
          <Link to={isLogin ? '/register' : '/login'}>{isLogin ? 'Sign up' : 'Log in'}</Link>
        </p>
      </section>
    </main>
  )
}

export default Auth
