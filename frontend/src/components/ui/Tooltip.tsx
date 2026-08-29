import { useState } from 'react'
import type { ReactNode } from 'react'

import { cn } from './cn'

export interface TooltipProps {
  content: ReactNode
  children: ReactNode
  side?: 'top' | 'bottom'
  className?: string
}

/**
 * CSS-only positioning against the trigger. Kept deliberately simple: the app never needs a
 * tooltip inside an overflow-hidden scroll container, which is the case that would demand a
 * portal and a positioning library.
 */
export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const [open, setOpen] = useState(false)

  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          className={cn(
            'pointer-events-none absolute left-1/2 z-50 w-max max-w-xs -translate-x-1/2',
            'animate-fade-in rounded-sm bg-accent-deep px-2 py-1 text-caption text-white shadow-mid',
            side === 'top' ? 'bottom-full mb-1.5' : 'top-full mt-1.5',
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}
