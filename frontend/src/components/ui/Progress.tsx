import { cn } from './cn'

const TONES = {
  accent: 'bg-accent',
  success: 'bg-status-success',
  danger: 'bg-status-danger',
  warning: 'bg-status-warning',
} as const

export interface ProgressProps {
  /** 0 to 100. Ignored when `indeterminate` is set. */
  value?: number
  tone?: keyof typeof TONES
  /** Use while work is happening but no meaningful percentage exists. */
  indeterminate?: boolean
  label?: string
  className?: string
}

export function Progress({
  value = 0,
  tone = 'accent',
  indeterminate = false,
  label,
  className,
}: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value))

  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={indeterminate ? undefined : clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn('h-1.5 w-full overflow-hidden rounded-full bg-surface-border', className)}
    >
      {indeterminate ? (
        <div
          className={cn('h-full w-1/3 animate-shimmer rounded-full', TONES[tone])}
          style={{
            backgroundImage:
              'linear-gradient(90deg, transparent, currentColor, transparent)',
            backgroundSize: '200% 100%',
          }}
        />
      ) : (
        <div
          className={cn('h-full rounded-full transition-[width] duration-500 ease-out', TONES[tone])}
          style={{ width: `${clamped}%` }}
        />
      )}
    </div>
  )
}
