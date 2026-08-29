import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { TriangleAlert } from 'lucide-react'

import { Button } from '@/components/ui'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[MCIE] Unhandled UI error', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="flex min-h-screen items-center justify-center bg-surface px-6">
        <div className="max-w-md text-center">
          <TriangleAlert className="mx-auto h-10 w-10 text-status-danger" />
          <h1 className="mt-4 text-h2 text-text-primary">Something broke in the interface</h1>
          <p className="mt-2 text-body-sm text-text-secondary">
            The compliance engine itself is unaffected. Reloading usually clears this.
          </p>
          <pre className="mt-4 overflow-x-auto rounded border border-surface-border bg-surface-card p-3 text-left text-caption text-text-tertiary">
            {this.state.error.message}
          </pre>
          <Button className="mt-5" onClick={() => window.location.reload()}>
            Reload the page
          </Button>
        </div>
      </div>
    )
  }
}
