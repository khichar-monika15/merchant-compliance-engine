import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { Button, Input, cn } from '@/components/ui'

import { AuthPanel } from './AuthPanel'

function strength(pw: string): { score: 0 | 1 | 2 | 3; label: string; tone: string } {
  if (pw.length < 8) return { score: 1, label: 'Too short', tone: 'bg-status-danger' }
  const varied = /[A-Z]/.test(pw) && /[0-9]/.test(pw)
  if (pw.length >= 12 && varied) return { score: 3, label: 'Strong', tone: 'bg-status-success' }
  if (varied || pw.length >= 10) return { score: 2, label: 'Fair', tone: 'bg-status-warning' }
  return { score: 1, label: 'Weak', tone: 'bg-status-warning' }
}

export function SignupPage() {
  const { signup, pending } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const pw = strength(password)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!name.trim()) return setError('Enter your name')
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError('Enter a valid email address')
    if (password.length < 8) return setError('Use at least 8 characters')

    const result = await signup(name, email, password)
    if (result.ok) navigate('/dashboard', { replace: true })
    else setError(result.error)
  }

  return (
    <AuthPanel
      title="Create an account"
      subtitle="Lives in this browser tab only. Closing the tab discards it."
      footer={
        <>
          Already have one?{' '}
          <Link to="/login" className="text-accent hover:text-accent-hover">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Input
          label="Full name"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <div>
          <Input
            label="Password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            hint="Any password of 8 or more characters works. Nothing is sent to a server."
          />
          {password.length > 0 && (
            <div className="mt-2 flex items-center gap-2">
              <div className="flex h-1 flex-1 gap-1">
                {[1, 2, 3].map((i) => (
                  <span
                    key={i}
                    className={cn(
                      'h-full flex-1 rounded-full',
                      i <= pw.score ? pw.tone : 'bg-surface-border',
                    )}
                  />
                ))}
              </div>
              <span className="text-caption text-text-tertiary">{pw.label}</span>
            </div>
          )}
        </div>
        {error && <p className="text-caption text-status-danger">{error}</p>}
        <Button type="submit" fullWidth size="lg" loading={pending === 'signup'}>
          Create account
        </Button>
      </form>
    </AuthPanel>
  )
}
