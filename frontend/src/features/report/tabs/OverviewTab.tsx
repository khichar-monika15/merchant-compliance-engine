import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

import type { GapItem, ReadinessReport } from '@/api/types'
import { Badge, Card, CardHeader, EmptyState, SEVERITY_VARIANT, cn } from '@/components/ui'

function ScoreBars({ report }: { report: ReadinessReport }) {
  return (
    <Card>
      <CardHeader
        title="Score breakdown"
        subtitle="The weights the engine actually used, not a recomputation."
      />
      <ul className="space-y-3">
        {report.score_breakdown.map((c) => (
          <li key={c.label}>
            <div className="mb-1 flex items-baseline justify-between gap-2">
              <span className="text-body-sm text-text-primary">
                {c.label}
                <span className="ml-1.5 text-caption text-text-tertiary">
                  {Math.round(c.weight * 100)}%
                </span>
              </span>
              <span className="font-mono text-body-sm text-text-secondary">{c.score}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-border">
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-700"
                style={{ width: `${Math.max(0, Math.min(100, c.score))}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function GapRow({ gap }: { gap: GapItem }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="border-b border-surface-border-subtle last:border-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-hover"
      >
        {open ? (
          <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-text-tertiary" />
        ) : (
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-text-tertiary" />
        )}
        <span className="min-w-0 flex-1 text-body-sm text-text-primary">{gap.title}</span>
        <Badge variant={SEVERITY_VARIANT[gap.severity] ?? 'neutral'}>{gap.severity}</Badge>
      </button>
      {open && (
        <div className="space-y-2 px-4 pb-4 pl-11">
          <p className="text-body-sm text-text-secondary">{gap.description}</p>
          {gap.fix_suggestion && (
            <p className="rounded border border-surface-border bg-surface-raised p-3 text-body-sm text-text-secondary">
              <span className="text-caption uppercase text-text-tertiary">How to fix</span>
              <br />
              {gap.fix_suggestion}
            </p>
          )}
        </div>
      )}
    </li>
  )
}

export function OverviewTab({ report }: { report: ReadinessReport }) {
  const critical = report.critical_gaps ?? []
  const warnings = report.warnings ?? []

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
      <div className="space-y-4">
        <ScoreBars report={report} />

        <Card>
          <CardHeader title="Estimated remediation" />
          <p className="text-body text-text-primary">{report.estimated_fix_time}</p>
          <div className="mt-4 flex gap-3">
            <div className="flex-1 rounded border border-status-danger/30 bg-status-danger-muted p-3">
              <p className="text-h2 text-status-danger">{critical.length}</p>
              <p className="text-caption uppercase text-text-tertiary">Critical</p>
            </div>
            <div className="flex-1 rounded border border-status-warning/30 bg-status-warning-muted p-3">
              <p className="text-h2 text-status-warning">{warnings.length}</p>
              <p className="text-caption uppercase text-text-tertiary">Warnings</p>
            </div>
          </div>
        </Card>
      </div>

      <Card padded={false}>
        <div className="px-5 pt-5">
          <CardHeader
            title="Gap analysis"
            subtitle="Every finding, most severe first. Expand for the fix."
            className="mb-3"
          />
        </div>
        {critical.length + warnings.length === 0 ? (
          <EmptyState
            title="No gaps found"
            description="This merchant meets every check the engine performs."
          />
        ) : (
          <ul className={cn('pb-1')}>
            {[...critical, ...warnings].map((gap, i) => (
              <GapRow key={`${gap.title}-${i}`} gap={gap} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
