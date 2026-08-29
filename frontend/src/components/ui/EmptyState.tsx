import type { ReactNode } from 'react'

import { cn } from './cn'

export interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 px-6 py-14 text-center',
        className,
      )}
    >
      {icon && <div className="text-text-tertiary">{icon}</div>}
      <h3 className="text-h3 text-text-primary">{title}</h3>
      {description && (
        <p className="max-w-sm text-body-sm text-text-secondary">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
