import { useState } from 'react'
import { GapItem, Severity } from '../types'

interface Props {
  gaps: GapItem[]
  estimatedFixTime: string
}

const severityOrder: Severity[] = ['critical', 'warning', 'info', 'pass']
const severityStyles: Record<Severity, string> = {
  critical: 'bg-red-50 border-red-200 text-red-700',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  info: 'bg-blue-50 border-blue-200 text-blue-700',
  pass: 'bg-green-50 border-green-200 text-green-700',
}

const severityLabel: Record<Severity, string> = {
  critical: 'CRITICAL',
  warning: 'WARNING',
  info: 'INFO',
  pass: 'PASS',
}

export function GapAnalysis({ gaps, estimatedFixTime }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  const sorted = [...gaps].sort(
    (a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity),
  )

  const counts = severityOrder.reduce(
    (acc, s) => {
      acc[s] = gaps.filter((g) => g.severity === s).length
      return acc
    },
    {} as Record<Severity, number>,
  )

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex justify-between items-start mb-4">
        <h2 className="text-lg font-semibold">Gap Analysis</h2>
        <span className="text-sm text-gray-500">{estimatedFixTime}</span>
      </div>
      <div className="flex gap-3 mb-4 flex-wrap">
        {severityOrder
          .filter((s) => counts[s] > 0)
          .map((s) => (
            <span
              key={s}
              className={`text-xs px-2 py-1 rounded-full border font-medium ${severityStyles[s]}`}
            >
              {counts[s]} {severityLabel[s]}
            </span>
          ))}
      </div>
      {sorted.length === 0 ? (
        <p className="text-sm text-gray-500">No gaps found.</p>
      ) : (
        <div className="space-y-2">
          {sorted.map((gap, i) => (
            <div
              key={i}
              className={`border rounded-lg p-3 cursor-pointer ${severityStyles[gap.severity]}`}
              onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
            >
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">{gap.title}</span>
                <span className="text-xs opacity-70">{gap.category.toUpperCase()}</span>
              </div>
              {expandedIdx === i && (
                <div className="mt-2 text-sm opacity-90 space-y-1">
                  <p>{gap.description}</p>
                  {gap.fix_suggestion && (
                    <p><strong>Fix:</strong> {gap.fix_suggestion}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
