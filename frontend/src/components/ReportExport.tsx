import { GapItem, ReadinessReport } from '../types'

interface Props {
  report: ReadinessReport
  gaps: GapItem[]
}

/** Revoking on the same tick as click() aborts the download in Firefox and older Safari. */
function download(content: string, mimeType: string, filename: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

export function ReportExport({ report, gaps }: Props) {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  const basename = `mcie-report-grade-${report.grade}-${stamp}`

  const exportJSON = () => {
    download(JSON.stringify(report, null, 2), 'application/json', `${basename}.json`)
  }

  const exportMarkdown = () => {
    const summary = `# MCIE Compliance Report

Score: ${report.overall_score}/100  Grade: ${report.grade}
Estimated fix time: ${report.estimated_fix_time}

## Gaps (${gaps.length})
${gaps.map((g) => `- [${g.severity.toUpperCase()}] ${g.title}: ${g.description}`).join('\n')}

## KYC
Consistent: ${report.kyc_details?.overall_consistent ? 'yes' : 'no'}
${(report.kyc_details?.common_mismatches ?? []).map((m) => `- ${m}`).join('\n')}

## PCI DSS surface
Security score: ${report.pci_details?.security_score ?? 'n/a'}/100
Third-party scripts: ${report.pci_details?.third_party_scripts ?? 0} (${report.pci_details?.scripts_without_sri ?? 0} without SRI)

## Generated policies
${(report.generated_policies?.generated_policies ?? []).map((p) => `- ${p.policy_type} (${p.word_count} words)`).join('\n') || 'None generated'}

## Audit trail
${(report.audit_trail ?? []).map((e) => `- ${e.timestamp} ${e.agent}: ${e.result}`).join('\n')}
`
    download(summary, 'text/markdown', `${basename}.md`)
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
