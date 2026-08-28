import { KYCMatch, KYCResult } from '../types'

interface Props {
  kyc: KYCResult
}

function MatchRow({ label, match }: { label: string; match: KYCMatch }) {
  return (
    <div className={`border rounded-lg p-3 ${match.match ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
      <p className="text-xs font-medium text-gray-500 mb-2">{label}</p>
      <div className="grid grid-cols-2 gap-2 text-sm mb-2">
        <div>
          <p className="text-xs text-gray-400 mb-1">Normalised A</p>
          <p className="font-mono text-xs">{match.normalized_a}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-1">Normalised B</p>
          <p className="font-mono text-xs">{match.normalized_b}</p>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">Similarity: {Math.round(match.similarity * 100)}%</span>
        <span className={match.match ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
          {match.match ? 'Match' : 'Mismatch'}
        </span>
      </div>
      {match.issues.length > 0 && (
        <ul className="mt-2 space-y-1">
          {match.issues.map((issue, i) => (
            <li key={i} className="text-xs text-red-600">• {issue}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function KYCPanel({ kyc }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex justify-between items-start mb-4">
        <h2 className="text-lg font-semibold">KYC Name Consistency</h2>
        <span className={`text-sm font-medium px-2 py-1 rounded-full ${kyc.overall_consistent ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {kyc.overall_consistent ? 'Consistent' : 'Mismatch'}
        </span>
      </div>

      {kyc.common_mismatches.length > 0 && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-xs font-medium text-red-700 mb-1">Name mismatches found:</p>
          <ul className="space-y-1">
            {kyc.common_mismatches.map((m, i) => (
              <li key={i} className="text-xs text-red-600">• {m}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-3">
        <MatchRow label="PAN vs GST" match={kyc.pan_gst_match} />
        <MatchRow label="GST vs Bank" match={kyc.gst_bank_match} />
        <MatchRow label="PAN vs Bank" match={kyc.pan_bank_match} />
      </div>
    </div>
  )
}
