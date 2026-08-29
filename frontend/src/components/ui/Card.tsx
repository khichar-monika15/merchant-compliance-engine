import { forwardRef } from 'react'
import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './cn'

const GLOWS = {
  accent: 'shadow-glow-accent',
  success: 'shadow-glow-success',
  danger: 'shadow-glow-danger',
} as const

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  glow?: keyof typeof GLOWS
  interactive?: boolean
  padded?: boolean
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { glow, interactive = false, padded = true, className, children, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        'rounded-lg border border-surface-border bg-surface-card',
        padded && 'p-5',
        interactive &&
          'transition-colors duration-150 hover:border-surface-active hover:shadow-low',
        glow && GLOWS[glow],
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
})

export interface CardHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  action?: ReactNode
  className?: string
}

export function CardHeader({ title, subtitle, action, className }: CardHeaderProps) {
  return (
    <div className={cn('mb-4 flex items-start justify-between gap-4', className)}>
      <div className="min-w-0">
        <h3 className="text-h3 text-text-primary">{title}</h3>
        {subtitle && <p className="mt-1 text-body-sm text-text-secondary">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
