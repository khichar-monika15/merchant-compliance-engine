import { useEffect, useRef, useState } from 'react'

import { cn } from './cn'

export interface MenuItem {
  label: string
  description?: string
  icon?: React.ReactNode
  onSelect: () => void
}

export interface MenuProps {
  trigger: React.ReactNode
  items: MenuItem[]
  align?: 'left' | 'right'
  label?: string
}

/**
 * A small dropdown. Closes on outside click, on Escape, and after a selection, so it cannot be
 * left open behind a print dialog or a download.
 */
export function Menu({ trigger, items, align = 'right', label = 'Menu' }: MenuProps) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    function onPointerDown(event: MouseEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div ref={root} className="relative">
      <div onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open}>
        {trigger}
      </div>

      {open && (
        <div
          role="menu"
          aria-label={label}
          className={cn(
            'absolute z-40 mt-2 w-60 max-w-[calc(100vw-2rem)] overflow-hidden rounded-lg',
            'border border-surface-border bg-surface-raised shadow-lg',
            // Right-aligning below the sm breakpoint pushed the panel off the left edge, because
            // the header stacks and the trigger moves to the left there.
            align === 'right' ? 'left-0 sm:left-auto sm:right-0' : 'left-0',
          )}
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={cn(
                'flex w-full items-start gap-3 px-4 py-3 text-left',
                'hover:bg-surface-hover focus:bg-surface-hover focus:outline-none',
              )}
              onClick={() => {
                setOpen(false)
                item.onSelect()
              }}
            >
              {item.icon && <span className="mt-0.5 shrink-0 text-text-tertiary">{item.icon}</span>}
              <span className="min-w-0">
                <span className="block text-body-sm text-text-primary">{item.label}</span>
                {item.description && (
                  <span className="block text-caption text-text-secondary">{item.description}</span>
                )}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
