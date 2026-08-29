import { cn } from './cn'

export interface SkeletonProps {
  className?: string
  /** Renders n stacked bars with the last one shortened, for text blocks. */
  lines?: number
}

export function Skeleton({ className, lines }: SkeletonProps) {
  const bar = (
    <div
      className={cn(
        'animate-shimmer rounded bg-surface-hover',
        'bg-[linear-gradient(90deg,transparent,rgba(148,163,184,0.08),transparent)] bg-[length:200%_100%]',
        !lines && 'h-4 w-full',
        className,
      )}
    />
  )

  if (!lines) return bar

  return (
    <div className="flex flex-col gap-2" aria-hidden>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className={cn(
            'h-4 animate-shimmer rounded bg-surface-hover',
            'bg-[linear-gradient(90deg,transparent,rgba(148,163,184,0.08),transparent)] bg-[length:200%_100%]',
            i === lines - 1 ? 'w-2/3' : 'w-full',
          )}
        />
      ))}
    </div>
  )
}
