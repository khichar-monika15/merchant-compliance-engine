import { Loader2 } from 'lucide-react'

import { cn } from './cn'

const SIZES = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-10 w-10',
} as const

export interface SpinnerProps {
  size?: keyof typeof SIZES
  className?: string
  label?: string
}

export function Spinner({ size = 'md', className, label = 'Loading' }: SpinnerProps) {
  return (
    <Loader2
      role="status"
      aria-label={label}
      className={cn('animate-spin text-accent', SIZES[size], className)}
    />
  )
}
