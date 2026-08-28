import { PCIResult } from '../types'

interface Props {
  pci: PCIResult
}

const riskBadge: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-red-100 text-red-700',
  unknown: 'bg-gray-100 text-gray-600',
}

const SECURITY_HEADERS = ['content-security-policy', 'strict-transport-security', 'x-frame-options', 'x-content-type-options', 'referrer-policy']

export function PCIReport({ pci }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
      <div className="flex justify-between items-start">
        <h2 className="text-lg font-semibold">PCI DSS Surface Scan</h2>
        <span className="text-sm font-semibold text-gray-700">Score: {Math.round(pci.overall_score)}/100</span>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-600 mb-2">Script Inventory ({pci.script_count} total)</h3>
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
              {pci.scripts.map((s, i) => (
                <tr key={i}>
                  <td className="py-2 font-mono max-w-xs truncate" title={s.src}>{s.domain || s.src}</td>
                  <td className="py-2 text-gray-500">{s.is_third_party ? '3rd party' : '1st party'}</td>
                  <td className="py-2"><span className={`px-1.5 py-0.5 rounded text-xs ${riskBadge[s.risk_level]}`}>{s.risk_level}</span></td>
                  <td className="py-2">{s.has_sri ? <span className="text-green-600">Yes</span> : <span className="text-red-500">No</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-600 mb-2">Security Headers</h3>
        <div className="space-y-2">
          {SECURITY_HEADERS.map((header) => {
            const val = pci.security_headers[header]
            return (
              <div key={header} className="flex justify-between items-center text-sm">
                <span className="font-mono text-gray-700 text-xs">{header}</span>
                {val ? (
                  <span className="text-green-600 text-xs truncate max-w-xs" title={val}>Present</span>
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
