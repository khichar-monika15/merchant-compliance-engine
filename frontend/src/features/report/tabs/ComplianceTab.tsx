import { Check, ExternalLink, X } from 'lucide-react'

import type { ComplianceCheck, ComplianceResult } from '@/api/types'
import { Badge, Card, CardHeader, SEVERITY_VARIANT, cn } from '@/components/ui'

const CHECK_ORDER: Array<{ key: keyof ComplianceResult; requirement: string }> = [
  { key: 'refund_policy', requirement: 'RBI-001' },
  { key: 'privacy_policy', requirement: 'RBI-002' },
  { key: 'terms_conditions', requirement: 'RBI-003' },
  { key: 'contact_info', requirement: 'RBI-004' },
  { key: 'gst_display', requirement: 'RBI-005' },
]

function QualityMeter({ score }: { score: number }) {
  const tone = score >= 7 ? 'bg-status-success' : score >= 5 ? 'bg-status-warning' : 'bg-status-danger'
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-1.5 w-24 gap-0.5">
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className={cn('h-full flex-1 rounded-sm', i < score ? tone : 'bg-surface-border')}
          />
        ))}
      </div>
      <span className="font-mono text-caption text-text-secondary">{score}/10</span>
    </div>
  )
}

function CheckRow({ check, requirement }: { check: ComplianceCheck; requirement: string }) {
  const passing = check.found && check.quality_score >= 7

  return (
    <li className="border-b border-surface-border-subtle px-5 py-4 last:border-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
            {passing ? (
              <Check className="h-4 w-4 text-status-success" />
            ) : (
              <X className="h-4 w-4 text-status-danger" />
            )}
          </span>
          <div className="min-w-0">
            <p className="text-body-sm text-text-primary">
              <span className="mr-2 font-mono text-caption text-text-tertiary">
                {check.check_id || requirement}
              </span>
              {check.name}
            </p>
            {check.url && (
              <a
                href={check.url}
                target="_blank"
                rel="noreferrer"
                className="mt-0.5 inline-flex items-center gap-1 font-mono text-caption text-accent hover:text-accent-hover"
              >
                {check.url}
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {check.found && <QualityMeter score={check.quality_score} />}
          <Badge variant={passing ? 'success' : SEVERITY_VARIANT[check.severity] ?? 'neutral'}>
            {check.found ? (passing ? 'pass' : 'inadequate') : 'missing'}
          </Badge>
        </div>
      </div>

      {check.issues.length > 0 && (
        <ul className="mt-3 space-y-1 pl-8">
          {check.issues.map((issue, i) => (
            <li key={i} className="text-caption text-text-secondary">
              {issue}
            </li>
          ))}
        </ul>
      )}

      {check.details && (
        <p className="mt-2 pl-8 text-caption text-text-tertiary">{check.details}</p>
      )}
    </li>
  )
}

export function ComplianceTab({ compliance }: { compliance: ComplianceResult }) {
  return (
    <div className="space-y-4">
      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-border px-5 py-4">
          <div>
            <h3 className="text-h3 text-text-primary">RBI Merchant Due Diligence</h3>
            <p className="text-caption text-text-tertiary">
              Five checks from backend/knowledge/rbi_mdd_checklist.json. Name consistency is
              RBI-006 and appears on the KYC tab.
            </p>
          </div>
          <div className="text-right">
            <p className="text-h2 text-text-primary">{compliance.overall_score}</p>
            <p className="text-caption uppercase text-text-tertiary">out of 100</p>
          </div>
        </div>

        <ul>
          {CHECK_ORDER.map(({ key, requirement }) => {
            const check = compliance[key] as ComplianceCheck
            if (!check) return null
            return <CheckRow key={requirement} check={check} requirement={requirement} />
          })}
        </ul>
      </Card>

      {compliance.business_category && (
        <Card>
          <CardHeader title="Detected business category" />
          <p className="font-mono text-body-sm text-text-primary">{compliance.business_category}</p>
          <p className="mt-1 text-caption text-text-tertiary">
            Selects which policy checklist variant applies, for example a SaaS refund policy rather
            than an e-commerce one.
          </p>
        </Card>
      )}
    </div>
  )
}
