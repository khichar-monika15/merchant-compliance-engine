import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './cn'

const VARIANTS = {
  critical: 'bg-status-danger-muted text-status-danger border-status-danger/30',
  warning: 'bg-status-warning-muted text-status-warning border-status-warning/30',
  success: 'bg-status-success-muted text-status-success border-status-success/30',
  info: 'bg-status-info-muted text-status-info border-status-info/30',
  neutral: 'bg-surface-hover text-text-secondary border-surface-border',
} as const

/** Backend `Severity` values map straight onto badge variants. */
export const SEVERITY_VARIANT: Record<string, keyof typeof VARIANTS> = {
  critical: 'critical',
  warning: 'warning',
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: keyof typeof VARIANTS
  icon?: ReactNode
}

export function Badge({ variant = 'neutral', icon, className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
        'text-overline uppercase',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
    </span>
  )
}
