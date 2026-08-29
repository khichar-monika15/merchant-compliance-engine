import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, Radar } from 'lucide-react'

import { useAuth } from '@/auth/AuthContext'
import { Badge, Button, Card, EmptyState, cn } from '@/components/ui'
import { useScanList } from '@/scan/scanStore'

const GRADE_TONE: Record<string, string> = {
  A: 'text-grade-a',
  B: 'text-grade-b',
  C: 'text-grade-c',
  D: 'text-grade-d',
  F: 'text-grade-f',
}

const STATUS_VARIANT = {
  queued: 'neutral',
  running: 'info',
  completed: 'success',
  failed: 'critical',
} as const

export function DashboardHome() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const scans = useScanList()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 text-text-primary">Welcome back, {user?.name?.split(' ')[0]}</h1>
        <p className="mt-1 text-body-sm text-text-secondary">
          Pre-qualify a merchant before they reach onboarding.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card interactive glow="accent" className="flex flex-col justify-between">
          <div>
            <Radar className="h-6 w-6 text-accent" />
            <h2 className="mt-3 text-h3 text-text-primary">Run a compliance scan</h2>
            <p className="mt-1 text-body-sm text-text-secondary">
              Audit a merchant website against RBI and PCI DSS, and cross check their KYC names.
            </p>
          </div>
          <Button className="mt-4 self-start" onClick={() => navigate('/dashboard/scan')}>
            New scan
          </Button>
        </Card>

        <Card interactive className="flex flex-col justify-between">
          <div>
            <BookOpen className="h-6 w-6 text-text-secondary" />
            <h2 className="mt-3 text-h3 text-text-primary">What gets checked</h2>
            <p className="mt-1 text-body-sm text-text-secondary">
              Eleven checks with formal identifiers: six from the RBI Merchant Due Diligence
              checklist, five from PCI DSS v4.0.1 requirements 6.4.3 and 11.6.1.
            </p>
          </div>
          <Button
            variant="secondary"
            className="mt-4 self-start"
            onClick={() => navigate('/checks')}
          >
            See every check
          </Button>
        </Card>
      </div>

      <Card padded={false}>
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-4">
          <div>
            <h2 className="text-h3 text-text-primary">This session</h2>
            <p className="text-caption text-text-tertiary">
              Scans are held in this browser tab. The engine has no user accounts.
            </p>
          </div>
        </div>

        {scans.length === 0 ? (
          <EmptyState
            icon={<Radar className="h-12 w-12" />}
            title="No scans yet"
            description="Run your first compliance scan to see a merchant readiness score."
            action={<Button onClick={() => navigate('/dashboard/scan')}>Start first scan</Button>}
          />
        ) : (
          <ul className="divide-y divide-surface-border">
            {scans.map((scan) => (
              <li key={scan.jobId}>
                <Link
                  to={
                    scan.status === 'completed'
                      ? `/dashboard/report/${scan.jobId}`
                      : `/dashboard/scan/${scan.jobId}`
                  }
                  className="flex items-center gap-4 px-5 py-3 transition-colors hover:bg-surface-hover"
                >
                  <span className="min-w-0 flex-1 truncate font-mono text-body-sm text-text-primary">
                    {scan.merchant.website_url || scan.jobId}
                  </span>

                  <Badge variant={STATUS_VARIANT[scan.status]}>{scan.status}</Badge>

                  {scan.report && (
                    <span className="flex items-baseline gap-1.5">
                      <span className="text-body font-semibold text-text-primary">
                        {scan.report.overall_score}
                      </span>
                      <span
                        className={cn(
                          'text-body font-bold',
                          GRADE_TONE[scan.report.grade] ?? 'text-text-secondary',
                        )}
                      >
                        {scan.report.grade}
                      </span>
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
