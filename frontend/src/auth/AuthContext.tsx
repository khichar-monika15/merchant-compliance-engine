import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { useScanStore } from '@/scan/scanStore'

import { DEMO_USERS, initialsFor } from './demoUsers'
import type { DemoUser } from './demoUsers'

export type AuthStatus = 'authenticated' | 'anonymous'

export interface SessionUser {
  id: string
  email: string
  name: string
  role: string
  initials: string
}

export type AuthResult = { ok: true; user: SessionUser } | { ok: false; error: string }

interface AuthContextValue {
  status: AuthStatus
  user: SessionUser | null
  pending: 'login' | 'signup' | null
  login: (email: string, password: string) => Promise<AuthResult>
  signup: (name: string, email: string, password: string) => Promise<AuthResult>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

const SESSION_KEY = 'mcie.session'
const USERS_KEY = 'mcie.demo-users'
const FAKE_LATENCY_MS = 450

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Private browsing can refuse writes. The session simply will not survive a reload.
  }
}

function toSessionUser(u: DemoUser): SessionUser {
  return { id: u.id, email: u.email, name: u.name, role: u.role, initials: u.initials }
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function AuthProvider({ children }: { children: ReactNode }) {
  // Lazy initialisers read storage synchronously, so there is never a "loading" flash that
  // would bounce a signed-in user to the login page on refresh.
  const [users, setUsers] = useState<DemoUser[]>(() => [
    ...DEMO_USERS,
    ...readJson<DemoUser[]>(USERS_KEY, []),
  ])
  const [user, setUser] = useState<SessionUser | null>(() => {
    const saved = readJson<{ userId?: string } | null>(SESSION_KEY, null)
    if (!saved?.userId) return null
    const all = [...DEMO_USERS, ...readJson<DemoUser[]>(USERS_KEY, [])]
    const found = all.find((u) => u.id === saved.userId)
    return found ? toSessionUser(found) : null
  })
  const [pending, setPending] = useState<'login' | 'signup' | null>(null)

  const login = useCallback(
    async (email: string, password: string): Promise<AuthResult> => {
      setPending('login')
      await wait(FAKE_LATENCY_MS)
      const found = users.find((u) => u.email.toLowerCase() === email.trim().toLowerCase())
      setPending(null)
      if (!found || found.password !== password) {
        return { ok: false, error: 'That email and password do not match a demo account.' }
      }
      const session = toSessionUser(found)
      setUser(session)
      writeJson(SESSION_KEY, { userId: found.id })
      return { ok: true, user: session }
    },
    [users],
  )

  const signup = useCallback(
    async (name: string, email: string, password: string): Promise<AuthResult> => {
      setPending('signup')
      await wait(FAKE_LATENCY_MS)
      const normalised = email.trim().toLowerCase()
      if (users.some((u) => u.email.toLowerCase() === normalised)) {
        setPending(null)
        return { ok: false, error: 'An account with that email already exists in this tab.' }
      }
      const created: DemoUser = {
        id: `u-${Date.now()}`,
        email: normalised,
        password,
        name: name.trim(),
        role: 'Onboarding Analyst',
        initials: initialsFor(name),
      }
      const nextCustom = [...readJson<DemoUser[]>(USERS_KEY, []), created]
      setUsers((prev) => [...prev, created])
      writeJson(USERS_KEY, nextCustom)
      const session = toSessionUser(created)
      setUser(session)
      writeJson(SESSION_KEY, { userId: created.id })
      setPending(null)
      return { ok: true, user: session }
    },
    [users],
  )

  const logout = useCallback(() => {
    setUser(null)
    try {
      sessionStorage.removeItem(SESSION_KEY)
    } catch {
      // Nothing to clear
    }
    // Closes any live socket and clears the scan list. Without this, signing in as the other
    // demo account would show the previous one's scans, implying a per-user isolation that the
    // backend cannot provide.
    useScanStore.getState().reset()
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      status: user ? 'authenticated' : 'anonymous',
      user,
      pending,
      login,
      signup,
      logout,
    }),
    [user, pending, login, signup, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
