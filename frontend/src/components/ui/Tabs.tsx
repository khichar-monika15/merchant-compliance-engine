
import { cn } from './cn'

export interface TabItem {
  id: string
  label: string
  count?: number
}

export interface TabsProps {
  tabs: TabItem[]
  active: string
  onChange: (id: string) => void
  className?: string
}

/**
 * Horizontal tabs with an underline indicator. The tab list is passed in rather than hardcoded
 * because every `*_details` block on the report is optional, so a partial report must render
 * fewer tabs instead of empty ones.
 */
export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div className={cn('border-b border-surface-border', className)}>
      <div
        role="tablist"
        className="-mb-px flex gap-1 overflow-x-auto"
      >
        {tabs.map((tab) => {
          const selected = tab.id === active
          return (
            <button
              key={tab.id}
              role="tab"
              type="button"
              aria-selected={selected}
              onClick={() => onChange(tab.id)}
              className={cn(
                'flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2.5',
                'text-body-sm font-medium transition-colors duration-150',
                selected
                  ? 'border-accent text-text-primary'
                  : 'border-transparent text-text-secondary hover:text-text-primary',
              )}
            >
              {tab.label}
              {tab.count != null && (
                <span
                  className={cn(
                    'rounded-full px-1.5 py-0.5 text-overline',
                    selected ? 'bg-accent-muted text-accent' : 'bg-surface-hover text-text-tertiary',
                  )}
                >
                  {tab.count}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
