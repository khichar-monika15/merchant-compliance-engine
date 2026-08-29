import { useEffect, useState } from 'react'

import { cn } from '@/components/ui'

const GRADE_COLOR: Record<string, string> = {
  A: '#04db7c',
  B: '#52c41a',
  C: '#f5a623',
  D: '#fa8c16',
  F: '#ff4d4f',
}

export const GRADE_TEXT: Record<string, string> = {
  A: 'text-grade-a',
  B: 'text-grade-b',
  C: 'text-grade-c',
  D: 'text-grade-d',
  F: 'text-grade-f',
}

const GRADE_WORD: Record<string, string> = {
  A: 'Ready to onboard',
  B: 'Good',
  C: 'Needs work',
  D: 'Significant gaps',
  F: 'Not ready',
}

export interface ScoreRingProps {
  score: number
  grade: string
  size?: number
  className?: string
}

export function ScoreRing({ score, grade, size = 132, className }: ScoreRingProps) {
  const [shown, setShown] = useState(0)
  const colour = GRADE_COLOR[grade] ?? '#97a0af'
  const radius = (size - 12) / 2
  const circumference = 2 * Math.PI * radius

  // Count up from zero so the number is legible as it settles rather than snapping into place.
  useEffect(() => {
    let frame = 0
    const start = performance.now()
    const duration = 900
    function tick(now: number) {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      setShown(Math.round(score * eased))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [score])

  return (
    <div className={cn('relative shrink-0', className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#1c2536"
          strokeWidth={8}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colour}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (circumference * shown) / 100}
          style={{ transition: 'stroke-dashoffset 120ms linear' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-h1 leading-none text-text-primary">{shown}</span>
        <span className={cn('text-h3 leading-tight', GRADE_TEXT[grade])}>{grade}</span>
        <span className="mt-0.5 text-caption text-text-tertiary">{GRADE_WORD[grade] ?? ''}</span>
      </div>
    </div>
  )
}
