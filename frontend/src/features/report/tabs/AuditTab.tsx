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

/**
 * The agents that do pure computation genuinely finish in under a millisecond, so rounding to a
 * whole number printed "0 ms" and read as a missing measurement rather than a fast one. Seconds
 * are used above a second because "4821 ms" is harder to scan than "4.8 s".
 */
function formatDuration(ms: number): string {
  if (ms < 1) return '<1 ms'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(1)} s`
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
          // Four fixed columns needed 408px, so this row pushed the whole report sideways on a
          // phone. Below sm the meta line wraps above the text; `sm:contents` dissolves the
          // wrapper again so the original four column row is unchanged on wider screens.
          <li key={i} className="px-5 py-3 sm:flex sm:gap-4">
            <div className="flex items-baseline gap-3 sm:contents">
              <span className="font-mono text-caption text-text-tertiary sm:w-20 sm:shrink-0">
                {formatTime(entry.timestamp)}
              </span>
              <span
                className={cn(
                  'text-caption font-medium sm:w-40 sm:shrink-0',
                  AGENT_TONE[entry.agent] ?? 'text-text-secondary',
                )}
              >
                {entry.agent}
              </span>
              {entry.duration_ms != null && (
                <span className="ml-auto font-mono text-caption text-text-tertiary sm:order-last sm:ml-0 sm:w-20 sm:text-right">
                  {formatDuration(entry.duration_ms)}
                </span>
              )}
            </div>
            <div className="mt-1 min-w-0 sm:mt-0 sm:flex-1">
              <span className="block text-body-sm text-text-primary">{entry.action}</span>
              <span className="block break-words text-caption text-text-secondary">
                {entry.result}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}
