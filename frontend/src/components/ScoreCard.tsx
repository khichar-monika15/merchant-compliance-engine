import { RadialBarChart, RadialBar, PolarAngleAxis } from 'recharts'
import { ScoreComponent } from '../types'

interface Props {
  score: number
  grade: string
  breakdown: ScoreComponent[]
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

export function ScoreCard({ score, grade, breakdown }: Props) {
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
            <span className={`text-lg font-bold ${gradeColor[grade] ?? 'text-gray-600'}`}>{grade}</span>
          </div>
        </div>
        <div className="flex-1 space-y-3">
          <p className={`text-sm font-medium ${gradeColor[grade] ?? 'text-gray-600'}`}>{gradeLabel[grade] ?? grade}</p>
          {breakdown.map(({ label, score: s, weight }) => (
            <div key={label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-600">
                  {label} <span className="text-gray-400">({Math.round(weight * 100)}%)</span>
                </span>
                <span className="font-medium">{s}</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full">
                <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(100, Math.max(0, s))}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
