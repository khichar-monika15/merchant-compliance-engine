import { ReadinessReport } from '../types'

interface Props {
  report: ReadinessReport
}

export function ReportExport({ report }: Props) {
  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mcie-report-${report.job_id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const summary = `# MCIE Compliance Report
URL: ${report.website_url}
Company: ${report.legal_name}
Score: ${report.overall_score}/100  Grade: ${report.grade}
Generated: ${new Date(report.created_at).toLocaleString()}

## Dimension Scores
RBI Compliance: ${Math.round(report.rbi_score)}/100
KYC Consistency: ${Math.round(report.kyc_score)}/100
PCI DSS: ${Math.round(report.pci_score)}/100
Integration Readiness: ${Math.round(report.integration_score)}/100

## Gaps (${report.gaps.length})
${report.gaps.map((g) => `- [${g.severity}] ${g.description}`).join('\n')}

Estimated fix time: ~${report.estimated_fix_hours} hours
`

  const exportMarkdown = () => {
    const blob = new Blob([summary], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mcie-report-${report.job_id}.md`
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
