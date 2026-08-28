import { AuditLogEntry } from '../types'

interface Props {
  log: AuditLogEntry[]
}

const agentColor: Record<string, string> = {
  WebCrawler: 'bg-indigo-100 text-indigo-700',
  ComplianceAuditor: 'bg-blue-100 text-blue-700',
  PCIScanner: 'bg-purple-100 text-purple-700',
  KYCValidator: 'bg-teal-100 text-teal-700',
  PolicyGenerator: 'bg-orange-100 text-orange-700',
  IntegrationAdvisor: 'bg-yellow-100 text-yellow-700',
  ReportGenerator: 'bg-gray-100 text-gray-700',
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}

export function AuditTrail({ log }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold mb-4">Audit Trail</h2>
      {log.length === 0 ? (
        <p className="text-sm text-gray-400">No audit events yet.</p>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {log.map((entry, i) => (
            <div key={i} className="flex gap-3 items-start text-sm">
              <span className="text-gray-400 text-xs mt-0.5 whitespace-nowrap w-20 flex-shrink-0">{formatTime(entry.timestamp)}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${agentColor[entry.agent] ?? 'bg-gray-100 text-gray-600'}`}>{entry.agent}</span>
              <span className="text-gray-600 flex-1">{entry.action}{entry.result ? ` — ${entry.result}` : ''}</span>
              {entry.duration_ms != null && <span className="text-gray-400 text-xs flex-shrink-0">{entry.duration_ms}ms</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
