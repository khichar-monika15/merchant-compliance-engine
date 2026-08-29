import type { GapItem, MerchantInput, ReadinessReport } from '@/api/types'

/**
 * The scanned URL is not a field on ReadinessReport, but the crawler records it in the audit
 * trail as "Crawled <url>". That makes the site recoverable for a report opened from a link,
 * or served from SQLite in a later browser session, where this tab never held the input.
 */
export function siteFromReport(report: ReadinessReport): string {
  const entry = report.audit_trail?.find((e) => e.agent === 'WebCrawler')
  const match = entry?.action.match(/Crawled\s+(\S+)/)
  return match ? match[1] : ''
}

function slug(url: string): string {
  return (url || 'merchant').replace(/^https?:\/\//, '').replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '')
}

/**
 * Revoking the object URL on the same tick as click() aborts the download in Firefox and older
 * Safari, and the anchor has to be in the document for the click to register at all.
 */
function download(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

export function exportJson(report: ReadinessReport, merchant: MerchantInput, jobId: string): void {
  const payload = { job_id: jobId, merchant, report }
  download(
    `mcie-${slug(merchant.website_url)}-${report.grade}.json`,
    JSON.stringify(payload, null, 2),
    'application/json',
  )
}

export function exportMarkdown(
  report: ReadinessReport,
  merchant: MerchantInput,
  jobId: string,
): void {
  const lines: string[] = [
    '# Merchant Compliance Readiness Report',
    '',
    `**Website:** ${merchant.website_url}`,
    `**Scan id:** ${jobId}`,
    `**Generated:** ${new Date().toISOString()}`,
    '',
    `## Score: ${report.overall_score}/100 (Grade ${report.grade})`,
    '',
    '| Component | Score | Weight |',
    '|---|---|---|',
    ...report.score_breakdown.map(
      (c) => `| ${c.label} | ${c.score} | ${Math.round(c.weight * 100)}% |`,
    ),
    '',
    `**Estimated remediation:** ${report.estimated_fix_time}`,
    '',
  ]

  const sections: Array<[string, GapItem[]]> = [
    ['Critical gaps', report.critical_gaps ?? []],
    ['Warnings', report.warnings ?? []],
  ]

  for (const [title, gaps] of sections) {
    if (gaps.length === 0) continue
    lines.push(`## ${title} (${gaps.length})`, '')
    for (const gap of gaps) {
      lines.push(`### ${gap.title}`, '', gap.description, '')
      if (gap.fix_suggestion) lines.push(`**Fix:** ${gap.fix_suggestion}`, '')
    }
  }

  if (report.audit_trail?.length) {
    lines.push('## Audit trail', '')
    for (const e of report.audit_trail) {
      lines.push(`- \`${e.timestamp}\` **${e.agent}** ${e.action}: ${e.result}`)
    }
    lines.push('')
  }

  download(
    `mcie-${slug(merchant.website_url)}-${report.grade}.md`,
    lines.join('\n'),
    'text/markdown',
  )
}
