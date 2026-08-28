import { KYCResult } from '../types'

interface Props {
  kyc: KYCResult
}

export function KYCPanel({ kyc }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex justify-between items-start mb-4">
        <h2 className="text-lg font-semibold">KYC Name Consistency</h2>
        <span className={`text-sm font-medium px-2 py-1 rounded-full ${kyc.all_consistent ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {kyc.all_consistent ? 'Consistent' : 'Mismatch'}
        </span>
      </div>
      <p className="text-sm text-gray-600 mb-4">{kyc.details}</p>
      <div className="space-y-3">
        {kyc.matches.map((m, i) => (
          <div key={i} className={`border rounded-lg p-3 ${m.match ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
            <div className="grid grid-cols-2 gap-2 text-sm mb-2">
              <div>
                <p className="text-xs text-gray-500 mb-1">Field A</p>
                <p className="font-mono font-medium">{m.field_a}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Field B</p>
                <p className="font-mono font-medium">{m.field_b}</p>
              </div>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Similarity: {Math.round(m.similarity * 100)}%</span>
              <span className={m.match ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
                {m.match ? 'Match' : 'Mismatch'}
              </span>
            </div>
            {m.issues.length > 0 && (
              <ul className="mt-2 space-y-1">
                {m.issues.map((issue, j) => (
                  <li key={j} className="text-xs text-red-600">• {issue}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
