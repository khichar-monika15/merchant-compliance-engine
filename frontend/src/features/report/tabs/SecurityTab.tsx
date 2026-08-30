import { Check, TriangleAlert, X } from 'lucide-react'

import type { PCIResult, SecurityHeaderInfo } from '@/api/types'
import { Badge, Card, CardHeader, cn } from '@/components/ui'

const HEADERS: Array<{ key: keyof PCIResult; label: string; why: string }> = [
  { key: 'csp_header', label: 'Content-Security-Policy', why: 'PCI DSS 11.6.1' },
  { key: 'hsts_header', label: 'Strict-Transport-Security', why: 'Forces HTTPS' },
  { key: 'x_frame_options', label: 'X-Frame-Options', why: 'Clickjacking' },
  { key: 'x_content_type', label: 'X-Content-Type-Options', why: 'MIME sniffing' },
  { key: 'referrer_policy', label: 'Referrer-Policy', why: 'URL leakage' },
]

const RISK_VARIANT = { high: 'critical', medium: 'warning', low: 'neutral' } as const

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-surface-border bg-surface-raised p-3">
      <p className="text-h2 text-text-primary">{value}</p>
      <p className="text-caption uppercase text-text-tertiary">{label}</p>
    </div>
  )
}

export function SecurityTab({ pci }: { pci: PCIResult }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader
            title="PCI DSS surface scan"
            subtitle="Requirements 6.4.3 and 11.6.1, checked from outside the site."
            action={
              <span className="text-h2 text-text-primary">
                {pci.security_score}
                <span className="text-caption text-text-tertiary">/100</span>
              </span>
            }
          />
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Scripts" value={pci.total_scripts} />
            <Stat label="Third party" value={pci.third_party_scripts} />
            <Stat label="No SRI" value={pci.scripts_without_sri} />
          </div>
        </Card>

        <Card padded={false}>
          <div className="px-5 pt-5">
            <CardHeader title="Security headers" className="mb-3" />
          </div>
          <ul className="pb-2">
            {HEADERS.map(({ key, label, why }) => {
              // The absent CSP shape has no `directives` key, so never assume one.
              const info = pci[key] as SecurityHeaderInfo | undefined
              const present = Boolean(info?.present)
              // A header can be present and still fall short, for example an HSTS max-age
              // below the minimum the checklist requires. The backend computes those reasons
              // and they used to be dropped here, so a present header looked simply fine.
              const shortfalls = present ? (info?.issues ?? []) : []
              return (
                <li key={String(key)} className="px-5 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 items-center gap-2">
                      {present && shortfalls.length === 0 ? (
                        <Check className="h-4 w-4 shrink-0 text-status-success" />
                      ) : present ? (
                        <TriangleAlert className="h-4 w-4 shrink-0 text-status-warning" />
                      ) : (
                        <X className="h-4 w-4 shrink-0 text-status-danger" />
                      )}
                      <span className="truncate font-mono text-caption text-text-primary">
                        {label}
                      </span>
                    </span>
                    <span className="shrink-0 text-caption text-text-tertiary">
                      {present
                        ? [info?.strength, info?.score != null ? `${info.score}/100` : null]
                            .filter(Boolean)
                            .join(' · ') || 'present'
                        : why}
                    </span>
                  </div>
                  {shortfalls.length > 0 && (
                    <ul className="mt-1 space-y-0.5 pl-6">
                      {shortfalls.map((issue) => (
                        <li key={issue} className="text-caption text-text-secondary">
                          {issue}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              )
            })}
          </ul>
        </Card>
      </div>

      {pci.critical_issues.length > 0 && (
        <Card>
          <CardHeader title="Findings" />
          <ol className="space-y-2">
            {pci.critical_issues.map((issue, i) => (
              <li key={i} className="flex gap-3 text-body-sm text-text-secondary">
                <span className="w-5 shrink-0 text-right font-mono text-caption text-text-tertiary">
                  {i + 1}.
                </span>
                <span className="min-w-0">{issue}</span>
              </li>
            ))}
          </ol>
        </Card>
      )}

      <Card padded={false}>
        <div className="px-5 pt-5">
          <CardHeader
            title="Script inventory"
            subtitle="PCI DSS 6.4.3 requires every payment page script to be inventoried and justified."
            className="mb-3"
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-body-sm">
            <thead className="border-y border-surface-border text-caption uppercase text-text-tertiary">
              <tr>
                <th className="px-5 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Party</th>
                <th className="px-3 py-2 font-medium">Category</th>
                <th className="px-3 py-2 font-medium">Risk</th>
                <th className="px-5 py-2 font-medium">SRI</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border-subtle">
              {pci.scripts_inventory.map((s, i) => (
                <tr key={i} className="hover:bg-surface-hover">
                  <td className="max-w-xs truncate px-5 py-2 font-mono text-caption text-text-primary">
                    {s.is_inline ? 'inline script' : (s.domain ?? s.src ?? 'unknown')}
                  </td>
                  <td className="px-3 py-2 text-caption text-text-secondary">
                    {s.is_inline ? 'inline' : s.is_first_party ? 'first' : 'third'}
                  </td>
                  <td className="px-3 py-2 text-caption text-text-secondary">
                    {s.category ?? 'unknown'}
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={RISK_VARIANT[s.risk_level ?? 'low'] ?? 'neutral'}>
                      {s.risk_level ?? 'low'}
                    </Badge>
                  </td>
                  <td className="px-5 py-2">
                    <span
                      className={cn(
                        'text-caption',
                        s.has_sri ? 'text-status-success' : 'text-text-tertiary',
                      )}
                    >
                      {s.is_inline ? 'n/a' : s.has_sri ? 'present' : 'missing'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
