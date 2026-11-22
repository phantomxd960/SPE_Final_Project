import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext.jsx'
import BuildFooter from '../components/BuildFooter.jsx'
import { ErrorMessage } from '../components/ui.jsx'

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate('/')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-shell">
      <form className="card login-card" onSubmit={submit}>
        <div className="login-brand">
          <img src="/favicon.svg" alt="" width="36" height="36" />
          <div>
            <h1>RegulationDiff</h1>
            <p className="muted">Regulation change detection and impact assessment</p>
          </div>
        </div>
        <ErrorMessage error={error} />
        <label className="field">
          <span>Email</span>
          <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <BuildFooter />
    </div>
  )
}
