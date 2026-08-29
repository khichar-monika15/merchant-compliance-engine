export interface DemoUser {
  id: string
  email: string
  password: string
  name: string
  role: string
  initials: string
}

/**
 * The compliance engine has no user model, no session and no auth of any kind. These accounts
 * exist only in this browser tab so the dashboard has an identity to display. Nothing is sent
 * to a server and nothing is created.
 */
export const DEMO_USERS: DemoUser[] = [
  {
    id: 'u-analyst',
    email: 'demo@mcie.dev',
    password: 'demo1234',
    name: 'Priya Raghavan',
    role: 'Onboarding Analyst',
    initials: 'PR',
  },
  {
    id: 'u-risk',
    email: 'admin@mcie.dev',
    password: 'admin1234',
    name: 'Arjun Mehta',
    role: 'Risk Operations',
    initials: 'AM',
  },
]

export function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'MC'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}
