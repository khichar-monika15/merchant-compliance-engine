import type { AuditLogEntry } from '@/api/types'
import { Card, CardHeader, cn } from '@/components/ui'

const AGENT_TONE: Record<string, string> = {
  WebCrawler: 'text-status-info',
  ComplianceAuditor: 'text-grade-b',
  PCIScanner: 'text-status-warning',
  KYCValidator: 'text-status-success',
  IntegrationAdvisor: 'text-accent',
  PolicyGenerator: 'text-grade-d',
  ReportGenerator: 'text-text-secondary',
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}

export function AuditTab({ log }: { log: AuditLogEntry[] }) {
  return (
    <Card padded={false}>
      <div className="px-5 pt-5">
        <CardHeader
          title="Audit trail"
          subtitle={`${log.length} entries. Every agent records what it did, what it found, and how long it took.`}
          className="mb-3"
        />
      </div>

      <ol className="divide-y divide-surface-border-subtle">
        {log.map((entry, i) => (
          <li key={i} className="flex gap-4 px-5 py-3">
            <span className="w-20 shrink-0 font-mono text-caption text-text-tertiary">
              {formatTime(entry.timestamp)}
            </span>
            <span
              className={cn(
                'w-40 shrink-0 text-caption font-medium',
                AGENT_TONE[entry.agent] ?? 'text-text-secondary',
              )}
            >
              {entry.agent}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-body-sm text-text-primary">{entry.action}</span>
              <span className="block break-words text-caption text-text-secondary">
                {entry.result}
              </span>
            </span>
            {entry.duration_ms != null && (
              <span className="w-20 shrink-0 text-right font-mono text-caption text-text-tertiary">
                {entry.duration_ms.toFixed(0)} ms
              </span>
            )}
          </li>
        ))}
      </ol>
    </Card>
  )
}
