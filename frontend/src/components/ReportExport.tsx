import { GapItem, ReadinessReport } from '../types'

interface Props {
  report: ReadinessReport
  gaps: GapItem[]
}

export function ReportExport({ report, gaps }: Props) {
  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mcie-report.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const summary = `# MCIE Compliance Report
Score: ${report.overall_score}/100  Grade: ${report.grade}

## Gaps (${gaps.length})
${gaps.map((g) => `- [${g.severity.toUpperCase()}] ${g.title}: ${g.description}`).join('\n')}

## Estimated fix time
${report.estimated_fix_time}
`

  const exportMarkdown = () => {
    const blob = new Blob([summary], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mcie-report.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex gap-3">
      <button
        onClick={exportJSON}
        className="text-sm px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
      >
        Export JSON
      </button>
      <button
        onClick={exportMarkdown}
        className="text-sm px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
      >
        Export Markdown
      </button>
    </div>
  )
}
