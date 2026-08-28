import { ProgressEvent } from '../types'

const AGENTS = ['WebCrawler', 'ComplianceAuditor', 'PCIScanner', 'KYCValidator', 'PolicyGenerator', 'IntegrationAdvisor', 'ReportGenerator']

interface Props {
  progress: ProgressEvent[]
  status: string
}

function agentStatus(agent: string, progress: ProgressEvent[]): 'pending' | 'running' | 'done' | 'error' {
  const events = progress.filter((e) => e.agent === agent || e.message?.includes(agent))
  if (events.some((e) => e.type === 'error')) return 'error'
  if (events.some((e) => e.type === 'complete' || e.message?.toLowerCase().includes('complete'))) return 'done'
  if (events.length > 0) return 'running'
  return 'pending'
}

const statusDot: Record<string, string> = {
  pending: 'bg-gray-200',
  running: 'bg-blue-500 animate-pulse',
  done: 'bg-green-500',
  error: 'bg-red-500',
}

export function ProgressTracker({ progress, status }: Props) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Agent Progress</h3>
      {AGENTS.map((agent) => {
        const s = agentStatus(agent, progress)
        return (
          <div key={agent} className="flex items-center gap-3">
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${statusDot[s]}`} />
            <span className="text-sm text-gray-700 flex-1">{agent}</span>
            <span className="text-xs text-gray-400 capitalize">{s}</span>
          </div>
        )
      })}
      {status === 'running' && (
        <div className="mt-4">
          <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full animate-pulse" style={{ width: `${Math.min(100, (progress.length / AGENTS.length) * 100)}%` }} />
          </div>
        </div>
      )}
      {progress.length > 0 && (
        <div className="mt-3 max-h-48 overflow-y-auto space-y-1">
          {progress.slice(-10).map((e, i) => (
            <p key={i} className="text-xs text-gray-500 font-mono">{e.message}</p>
          ))}
        </div>
      )}
    </div>
  )
}
