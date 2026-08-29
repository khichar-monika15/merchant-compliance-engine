import type { ProgressEvent, ScanStatus } from '@/api/types'

/**
 * Pipeline order as the backend actually emits it, which is not the order listed in CLAUDE.md:
 * IntegrationAdvisor completes at 65, before PolicyGenerator runs at 75.
 */
export const AGENT_ORDER = [
  'WebCrawler',
  'ComplianceAuditor',
  'PCIScanner',
  'KYCValidator',
  'IntegrationAdvisor',
  'PolicyGenerator',
  'ReportGenerator',
] as const

export type AgentName = (typeof AGENT_ORDER)[number]

/** These four run concurrently inside one `asyncio.gather` node. */
export const PARALLEL_GROUP: ReadonlySet<string> = new Set([
  'ComplianceAuditor',
  'PCIScanner',
  'KYCValidator',
  'IntegrationAdvisor',
])

/** Names that appear in the stream but are not agents and own no timeline row. */
export const SYSTEM_SENDERS: ReadonlySet<string> = new Set(['Orchestrator', 'Complete'])

export const AGENT_LABELS: Record<AgentName, { title: string; blurb: string }> = {
  WebCrawler: { title: 'Web Crawler', blurb: 'Fetches pages, scripts and headers' },
  ComplianceAuditor: { title: 'Compliance Auditor', blurb: 'RBI Merchant Due Diligence' },
  PCIScanner: { title: 'PCI Scanner', blurb: 'PCI DSS v4.0.1 surface checks' },
  KYCValidator: { title: 'KYC Validator', blurb: 'PAN, GST and bank name consistency' },
  IntegrationAdvisor: { title: 'Integration Advisor', blurb: 'Stack detection and starter code' },
  PolicyGenerator: { title: 'Policy Generator', blurb: 'Drafts the missing policy documents' },
  ReportGenerator: { title: 'Report Generator', blurb: 'Scores and aggregates the findings' },
}

export type AgentPhase = 'pending' | 'running' | 'done' | 'skipped' | 'failed' | 'not-run'

export interface AgentNode {
  name: AgentName
  phase: AgentPhase
  lastMessage: string | null
  finishedAt: string | null
  parallel: boolean
}

export interface Timeline {
  agents: AgentNode[]
  percent: number
  parallelGroupActive: boolean
  failure: { agent: string; message: string } | null
  systemEvents: ProgressEvent[]
  lastEventAt: number | null
}

function bucket(events: ProgressEvent[]): Map<string, ProgressEvent[]> {
  const map = new Map<string, ProgressEvent[]>()
  for (const e of events) {
    if (!e.agent) continue
    const list = map.get(e.agent)
    if (list) list.push(e)
    else map.set(e.agent, [e])
  }
  return map
}

function phaseFor(evts: ProgressEvent[] | undefined, name: AgentName, terminal: boolean): AgentPhase {
  if (!evts || evts.length === 0) {
    // The crawl abort path ends the graph after WebCrawler, so five agents legitimately never
    // run. Showing them as pending forever would be wrong.
    return terminal ? 'not-run' : 'pending'
  }
  if (evts.some((e) => e.type === 'error')) return 'failed'

  // `done === true`, not truthiness: the exception path omits `done` entirely.
  const finished = evts.find((e) => e.done === true)
  if (finished) {
    if (name === 'PolicyGenerator' && /skipped/i.test(finished.message ?? '')) return 'skipped'
    return 'done'
  }
  return 'running'
}

/**
 * Fold the flat event stream into per agent state.
 *
 * Pure and side effect free so it can be unit tested without a socket.
 */
export function buildTimeline(events: ProgressEvent[], status: ScanStatus): Timeline {
  const real = events.filter((e) => e.type !== 'ping')
  const systemEvents = real.filter((e) => !e.agent || SYSTEM_SENDERS.has(e.agent))
  const byAgent = bucket(real.filter((e) => e.agent && !SYSTEM_SENDERS.has(e.agent)))
  const terminal = status === 'completed' || status === 'failed'

  const agents: AgentNode[] = AGENT_ORDER.map((name) => {
    const evts = byAgent.get(name)
    const phase = phaseFor(evts, name, terminal)
    const finished = evts?.find((e) => e.done === true)
    return {
      name,
      phase,
      lastMessage: evts?.length ? (evts[evts.length - 1].message ?? null) : null,
      finishedAt: finished?.timestamp ?? null,
      parallel: PARALLEL_GROUP.has(name),
    }
  })

  // Error events carry progress -1, so they must not win the max.
  const pcts = real
    .map((e) => e.progress)
    .filter((p): p is number => typeof p === 'number' && p >= 0)
  let percent = pcts.length ? Math.min(100, Math.max(...pcts)) : 0
  if (status === 'completed') percent = 100

  const errorEvent = [...real].reverse().find((e) => e.type === 'error')
  const timestamps = real
    .map((e) => (e.timestamp ? Date.parse(e.timestamp) : NaN))
    .filter((n) => !Number.isNaN(n))

  return {
    agents,
    percent,
    parallelGroupActive: agents.some((a) => a.parallel && a.phase === 'running'),
    failure: errorEvent
      ? {
          agent: errorEvent.agent ?? 'Orchestrator',
          message: (errorEvent.message ?? 'Scan failed').replace(/^Error:\s*/, ''),
        }
      : null,
    systemEvents,
    lastEventAt: timestamps.length ? Math.max(...timestamps) : null,
  }
}
