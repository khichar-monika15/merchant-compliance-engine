import { useNavigate } from 'react-router-dom'
import { Compass } from 'lucide-react'

import { Button } from '@/components/ui'

export function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-surface px-6 text-center">
      <Compass className="h-10 w-10 text-text-tertiary" />
      <h1 className="text-h1 text-text-primary">This page does not exist</h1>
      <p className="max-w-sm text-body-sm text-text-secondary">
        The link may be out of date, or the scan it pointed to has expired.
      </p>
      <Button onClick={() => navigate('/dashboard')}>Back to dashboard</Button>
    </div>
  )
}
