import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { DEMO_USERS } from '@/auth/demoUsers'
import { safeRedirect } from '@/auth/redirect'
import { Button, Input } from '@/components/ui'

import { AuthPanel } from './AuthPanel'

export function LoginPage() {
  const { login, pending } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    const result = await login(email, password)
    if (result.ok) {
      navigate(safeRedirect((location.state as { from?: string } | null)?.from), { replace: true })
    } else {
      setError(result.error)
    }
  }

  return (
    <AuthPanel
      title="Sign in"
      subtitle="Demo sign in. No account is created and nothing is sent to a server."
      footer={
        <>
          Need an account?{' '}
          <Link to="/signup" className="text-accent hover:text-accent-hover">
            Sign up
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="demo@mcie.dev"
        />
        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-caption text-status-danger">{error}</p>}
        <Button type="submit" fullWidth size="lg" loading={pending === 'login'}>
          Sign in
        </Button>
      </form>

      <div className="mt-6 rounded border border-surface-border bg-surface-raised p-3">
        <p className="text-overline uppercase text-text-tertiary">Demo accounts</p>
        <ul className="mt-2 space-y-1.5">
          {DEMO_USERS.map((u) => (
            <li key={u.id} className="flex items-center justify-between gap-3">
              <span className="truncate font-mono text-caption text-text-secondary">
                {u.email} / {u.password}
              </span>
              <button
                type="button"
                className="shrink-0 text-caption text-accent hover:text-accent-hover"
                onClick={() => {
                  setEmail(u.email)
                  setPassword(u.password)
                }}
              >
                Use
              </button>
            </li>
          ))}
        </ul>
      </div>
    </AuthPanel>
  )
}
