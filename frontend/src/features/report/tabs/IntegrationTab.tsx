import { CircleCheck, CircleAlert } from 'lucide-react'

import type { IntegrationResult } from '@/api/types'
import { Badge, Card, CardHeader, CodeBlock } from '@/components/ui'
import { integrationMethodLabel, stackLabel } from '@/api/labels'

export function IntegrationTab({ integration }: { integration: IntegrationResult }) {
  const stacks = Object.entries(integration.detected_stack ?? {})
  const test = integration.test_payment_result ?? {}
  const testOk = Boolean((test as { success?: boolean }).success)
  const testError = (test as { error?: string }).error
  const orderId = (test as { order_id?: string }).order_id

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Detected stack" subtitle="Matched against tech_stack_signatures.json" />
          {stacks.length === 0 ? (
            <p className="text-body-sm text-text-secondary">No framework signals found.</p>
          ) : (
            <ul className="space-y-3">
              {stacks.map(([name, evidence]) => (
                <li key={name}>
                  <Badge variant="info">{stackLabel(name)}</Badge>
                  <ul className="mt-1.5 space-y-0.5">
                    {(evidence as string[]).map((e, i) => (
                      <li key={i} className="font-mono text-caption text-text-tertiary">
                        {e}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Recommended Razorpay path" />
          <p className="text-body text-text-primary">{integration.recommended_product}</p>
          <p className="mt-1 text-caption text-text-tertiary">
            {integrationMethodLabel(integration.integration_method)}
          </p>
          {integration.recommendation_reason && (
            <p className="mt-2 text-body-sm text-text-secondary">
              {integration.recommendation_reason}
            </p>
          )}
          {integration.docs_url && (
            <a
              href={integration.docs_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-body-sm text-accent hover:underline"
            >
              Razorpay documentation
            </a>
          )}

          <div className="mt-4 flex items-start gap-2 rounded border border-surface-border bg-surface-raised p-3">
            {testOk ? (
              <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-status-success" />
            ) : (
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-status-warning" />
            )}
            <div className="min-w-0">
              <p className="text-body-sm text-text-primary">
                {testOk ? 'Test order created' : 'No live test order'}
              </p>
              <p className="break-words text-caption text-text-tertiary">
                {testOk
                  ? `Razorpay order ${orderId}`
                  : (testError ??
                    'Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to place a real test order. Scans are unaffected.')}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {integration.starter_code && (
        <CodeBlock
          code={integration.starter_code}
          language={integration.starter_code_language}
          title={`Starter code for ${stackLabel(stacks[0]?.[0]) || 'this stack'}`}
        />
      )}
    </div>
  )
}
