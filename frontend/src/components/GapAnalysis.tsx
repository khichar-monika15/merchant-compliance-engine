import { useState } from 'react'
import { GapItem, Severity } from '../types'

interface Props {
  gaps: GapItem[]
  estimatedHours: number
}

const severityOrder: Severity[] = ['CRITICAL', 'WARNING', 'INFO', 'PASS']
const severityStyles: Record<Severity, string> = {
  CRITICAL: 'bg-red-50 border-red-200 text-red-700',
  WARNING: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  INFO: 'bg-blue-50 border-blue-200 text-blue-700',
  PASS: 'bg-green-50 border-green-200 text-green-700',
}

export function GapAnalysis({ gaps, estimatedHours }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)

  const sorted = [...gaps].sort((a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity))

  const counts = severityOrder.reduce((acc, s) => {
    acc[s] = gaps.filter((g) => g.severity === s).length
    return acc
  }, {} as Record<Severity, number>)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex justify-between items-start mb-4">
        <h2 className="text-lg font-semibold">Gap Analysis</h2>
        <span className="text-sm text-gray-500">Est. fix time: <strong>{estimatedHours}h</strong></span>
      </div>
      <div className="flex gap-3 mb-4">
        {severityOrder.filter((s) => counts[s] > 0).map((s) => (
          <span key={s} className={`text-xs px-2 py-1 rounded-full border font-medium ${severityStyles[s]}`}>
            {counts[s]} {s}
          </span>
        ))}
      </div>
      {sorted.length === 0 ? (
        <p className="text-sm text-gray-500">No gaps found.</p>
      ) : (
        <div className="space-y-2">
          {sorted.map((gap) => (
            <div key={gap.id} className={`border rounded-lg p-3 cursor-pointer ${severityStyles[gap.severity]}`} onClick={() => setExpanded(expanded === gap.id ? null : gap.id)}>
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">{gap.description}</span>
                <span className="text-xs opacity-70">{gap.category.toUpperCase()}</span>
              </div>
              {expanded === gap.id && (
                <div className="mt-2 text-sm opacity-90">
                  <p><strong>Fix:</strong> {gap.fix_hint}</p>
                  <p className="mt-1"><strong>Effort:</strong> ~{gap.estimated_hours}h</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
