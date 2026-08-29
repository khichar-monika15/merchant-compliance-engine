import { forwardRef, useId } from 'react'
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'

import { cn } from './cn'

const FIELD_BASE =
  'w-full rounded border bg-surface-raised px-3 text-body text-text-primary transition-colors ' +
  'placeholder:text-text-tertiary focus:outline-none focus:ring-0 disabled:opacity-50'

function fieldTone(invalid: boolean) {
  return invalid
    ? 'border-status-danger focus:border-status-danger'
    : 'border-surface-border focus:border-accent'
}

interface FieldShellProps {
  id: string
  label?: ReactNode
  hint?: ReactNode
  error?: string | null
  children: ReactNode
  className?: string
}

function FieldShell({ id, label, hint, error, children, className }: FieldShellProps) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label && (
        <label htmlFor={id} className="text-caption text-text-secondary">
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-caption text-status-danger">
          {error}
        </p>
      ) : (
        hint && <p className="text-caption text-text-tertiary">{hint}</p>
      )}
    </div>
  )
}

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: ReactNode
  hint?: ReactNode
  error?: string | null
  mono?: boolean
  containerClassName?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, mono = false, containerClassName, className, id, ...rest },
  ref,
) {
  const generated = useId()
  const fieldId = id ?? generated
  const invalid = Boolean(error)

  return (
    <FieldShell
      id={fieldId}
      label={label}
      hint={hint}
      error={error}
      className={containerClassName}
    >
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? `${fieldId}-error` : undefined}
        className={cn(FIELD_BASE, 'h-10', fieldTone(invalid), mono && 'font-mono', className)}
        {...rest}
      />
    </FieldShell>
  )
})

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: ReactNode
  hint?: ReactNode
  error?: string | null
  containerClassName?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, containerClassName, className, id, children, ...rest },
  ref,
) {
  const generated = useId()
  const fieldId = id ?? generated
  const invalid = Boolean(error)

  return (
    <FieldShell
      id={fieldId}
      label={label}
      hint={hint}
      error={error}
      className={containerClassName}
    >
      <select
        ref={ref}
        id={fieldId}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? `${fieldId}-error` : undefined}
        className={cn(FIELD_BASE, 'h-10 pr-8', fieldTone(invalid), className)}
        {...rest}
      >
        {children}
      </select>
    </FieldShell>
  )
})
