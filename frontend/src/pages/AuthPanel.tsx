import { Link } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'

export interface AuthPanelProps {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
}

export function AuthPanel({ title, subtitle, children, footer }: AuthPanelProps) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-accent-deep p-10 md:flex md:w-3/5">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 20%, rgba(13,148,251,0.35), transparent 45%), radial-gradient(circle at 80% 70%, rgba(4,219,124,0.18), transparent 40%)',
          }}
        />
        <Link to="/" className="relative flex items-center gap-2 text-white">
          <ShieldCheck className="h-6 w-6" />
          <span className="text-h3">MCIE</span>
        </Link>

        <div className="relative">
          <h2 className="max-w-md text-display text-white">Compliance intelligence, automated.</h2>
          <p className="mt-4 max-w-md text-body text-white/70">
            Seven agents audit a merchant website against RBI Merchant Due Diligence and PCI DSS
            v4.0.1, cross check the KYC names, and score onboarding readiness from A to F.
          </p>
        </div>

        <p className="relative text-caption text-white/50">
          11 compliance checks · 7 agents · about 20 seconds
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center bg-surface px-6 py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-h1 text-text-primary">{title}</h1>
          <p className="mb-6 mt-1 text-body-sm text-text-secondary">{subtitle}</p>
          {children}
          <p className="mt-6 text-center text-caption text-text-secondary">{footer}</p>
        </div>
      </div>
    </div>
  )
}
