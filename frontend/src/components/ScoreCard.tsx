import { RadialBarChart, RadialBar, PolarAngleAxis } from 'recharts'

interface Props {
  score: number
  grade: string
  rbiScore: number
  kycScore: number
  pciScore: number
  integrationScore: number
}

const gradeColor: Record<string, string> = {
  A: 'text-green-600',
  B: 'text-blue-600',
  C: 'text-yellow-600',
  D: 'text-orange-600',
  F: 'text-red-600',
}

const gradeLabel: Record<string, string> = {
  A: 'Excellent',
  B: 'Good',
  C: 'Needs Work',
  D: 'Poor',
  F: 'Failing',
}

export function ScoreCard({ score, grade, rbiScore, kycScore, pciScore, integrationScore }: Props) {
  const data = [{ value: score, fill: score >= 75 ? '#22c55e' : score >= 50 ? '#eab308' : '#ef4444' }]

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold mb-4">Readiness Score</h2>
      <div className="flex items-center gap-8">
        <div className="relative">
          <RadialBarChart width={160} height={160} innerRadius={50} outerRadius={75} data={data} startAngle={90} endAngle={-270}>
            <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
            <RadialBar background dataKey="value" cornerRadius={8} />
          </RadialBarChart>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold">{score}</span>
            <span className={`text-lg font-bold ${gradeColor[grade]}`}>{grade}</span>
          </div>
        </div>
        <div className="flex-1 space-y-3">
          <p className={`text-sm font-medium ${gradeColor[grade]}`}>{gradeLabel[grade]}</p>
          {[
            { label: 'RBI Compliance', score: rbiScore, weight: '40%' },
            { label: 'KYC Consistency', score: kycScore, weight: '25%' },
            { label: 'PCI DSS', score: pciScore, weight: '20%' },
            { label: 'Integration', score: integrationScore, weight: '15%' },
          ].map(({ label, score: s, weight }) => (
            <div key={label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-600">{label} <span className="text-gray-400">({weight})</span></span>
                <span className="font-medium">{Math.round(s)}</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full">
                <div className="h-full bg-blue-500 rounded-full" style={{ width: `${s}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
