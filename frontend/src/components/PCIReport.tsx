import { PCIResult, SecurityHeaderInfo } from '../types'

interface Props {
  pci: PCIResult
}

const riskBadge: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-red-100 text-red-700',
  unknown: 'bg-gray-100 text-gray-600',
}

const HEADERS: { key: keyof PCIResult; label: string }[] = [
  { key: 'csp_header', label: 'content-security-policy' },
  { key: 'hsts_header', label: 'strict-transport-security' },
  { key: 'x_frame_options', label: 'x-frame-options' },
  { key: 'x_content_type', label: 'x-content-type-options' },
  { key: 'referrer_policy', label: 'referrer-policy' },
]

export function PCIReport({ pci }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
      <div className="flex justify-between items-start">
        <h2 className="text-lg font-semibold">PCI DSS Surface Scan</h2>
        <span className="text-sm font-semibold text-gray-700">
          Score: {Math.round(pci.security_score)}/100
        </span>
      </div>

      {pci.critical_issues.length > 0 && (
        <div className="space-y-1">
          {pci.critical_issues.map((issue, i) => (
            <p key={i} className="text-xs text-red-600">⚠ {issue}</p>
          ))}
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold text-gray-600 mb-2">
          Script Inventory ({pci.total_scripts} total, {pci.third_party_scripts} third-party,{' '}
          {pci.scripts_without_sri} missing SRI)
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2 font-medium">Source</th>
                <th className="pb-2 font-medium">Type</th>
                <th className="pb-2 font-medium">Risk</th>
                <th className="pb-2 font-medium">SRI</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {pci.scripts_inventory.map((s, i) => (
                <tr key={i}>
                  <td className="py-2 font-mono max-w-xs truncate" title={s.src ?? ''}>
                    {s.domain || s.src || '(inline)'}
                  </td>
                  <td className="py-2 text-gray-500">
                    {s.is_inline ? 'inline' : s.is_first_party ? '1st party' : '3rd party'}
                  </td>
                  <td className="py-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${riskBadge[s.risk_level ?? 'unknown']}`}>
                      {s.risk_level ?? 'unknown'}
                    </span>
                  </td>
                  <td className="py-2">
                    {s.has_sri ? (
                      <span className="text-green-600">Yes</span>
                    ) : (
                      <span className="text-red-500">No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-600 mb-2">Security Headers</h3>
        <div className="space-y-2">
          {HEADERS.map(({ key, label }) => {
            const info = pci[key] as SecurityHeaderInfo
            return (
              <div key={label} className="flex justify-between items-center text-sm">
                <span className="font-mono text-gray-700 text-xs">{label}</span>
                {info?.present ? (
                  <span className="text-green-600 text-xs">Present</span>
                ) : (
                  <span className="text-red-500 text-xs">Missing</span>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
