import { Ban, Check, CircleAlert, Clock, Minus } from 'lucide-react'

import { Spinner, cn } from '@/components/ui'
import { AGENT_LABELS } from '@/scan/agentTimeline'
import type { AgentNode, AgentPhase, Timeline } from '@/scan/agentTimeline'

const PHASE_TEXT: Record<AgentPhase, string> = {
  pending: 'Waiting',
  running: 'Running',
  done: 'Done',
  skipped: 'Skipped, nothing to generate',
  failed: 'Failed',
  'not-run': 'Did not run',
}

function PhaseIcon({ phase }: { phase: AgentPhase }) {
  switch (phase) {
    case 'running':
      return <Spinner size="sm" />
    case 'done':
      return <Check className="h-4 w-4 text-status-success" />
    case 'skipped':
      return <Minus className="h-4 w-4 text-text-tertiary" />
    case 'failed':
      return <CircleAlert className="h-4 w-4 text-status-danger" />
    case 'not-run':
      return <Ban className="h-4 w-4 text-text-tertiary" />
    default:
      return <Clock className="h-4 w-4 text-text-tertiary" />
  }
}

function AgentRow({ node, indented }: { node: AgentNode; indented?: boolean }) {
  const label = AGENT_LABELS[node.name]
  const dim = node.phase === 'pending' || node.phase === 'not-run'

  return (
    <li className={cn('flex items-start gap-3 py-2', indented && 'pl-6')}>
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
        <PhaseIcon phase={node.phase} />
      </span>
      <span className="min-w-0 flex-1">
        <span className={cn('block text-body-sm', dim ? 'text-text-tertiary' : 'text-text-primary')}>
          {label.title}
        </span>
        <span className="block truncate text-caption text-text-tertiary">
          {node.lastMessage ?? label.blurb}
        </span>
      </span>
      <span
        className={cn(
          'shrink-0 text-caption',
          node.phase === 'failed' ? 'text-status-danger' : 'text-text-tertiary',
        )}
      >
        {PHASE_TEXT[node.phase]}
      </span>
    </li>
  )
}

export function AgentTimeline({ timeline }: { timeline: Timeline }) {
  const sequential = timeline.agents.filter((a) => !a.parallel)
  const parallel = timeline.agents.filter((a) => a.parallel)
  const crawler = sequential[0]
  const tail = sequential.slice(1)

  return (
    <ul className="divide-y divide-surface-border-subtle">
      {crawler && <AgentRow node={crawler} />}

      <li className="py-2">
        <div className="flex items-center gap-2 pb-1">
          <span className="text-overline uppercase text-text-tertiary">
            Parallel analysis
          </span>
          <span className="text-caption text-text-tertiary">
            {timeline.parallelGroupActive
              ? '4 agents running concurrently'
              : '4 agents, one asyncio.gather'}
          </span>
        </div>
        <ul className="border-l border-surface-border">
          {parallel.map((node) => (
            <AgentRow key={node.name} node={node} indented />
          ))}
        </ul>
      </li>

      {tail.map((node) => (
        <AgentRow key={node.name} node={node} />
      ))}
    </ul>
  )
}
