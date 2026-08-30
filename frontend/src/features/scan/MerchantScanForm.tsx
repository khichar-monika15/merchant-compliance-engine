import { useState } from 'react'
import { Radar } from 'lucide-react'

import { BUSINESS_TYPE_LABELS } from '@/api/labels'
import type { MerchantInput } from '@/api/types'
import { Button, Card, CardHeader, Input, Select } from '@/components/ui'
import { DEMO_SITES } from '@/scan/demoSites'

// Built from the shared label map so the form and the report cannot disagree about what a
// business type is called.
const BUSINESS_TYPES = [
  { value: '', label: 'Auto detect' },
  ...Object.entries(BUSINESS_TYPE_LABELS).map(([value, label]) => ({ value, label })),
]

const EMPTY: MerchantInput = {
  website_url: '',
  pan_name: '',
  gst_legal_name: '',
  bank_account_name: '',
  business_type: '',
}

type Errors = Partial<Record<keyof MerchantInput, string>>

/** The backend field is a Pydantic HttpUrl, so a bare host is a 422. Fix it before sending. */
function normaliseUrl(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return trimmed
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
}

function validate(v: MerchantInput): Errors {
  const errors: Errors = {}
  if (!v.website_url.trim()) errors.website_url = 'Enter the merchant website'
  else {
    try {
      new URL(normaliseUrl(v.website_url))
    } catch {
      errors.website_url = 'That does not look like a valid URL'
    }
  }
  if (!v.pan_name.trim()) errors.pan_name = 'Required for the KYC comparison'
  if (!v.gst_legal_name.trim()) errors.gst_legal_name = 'Required for the KYC comparison'
  if (!v.bank_account_name.trim()) errors.bank_account_name = 'Required for the KYC comparison'
  return errors
}

export interface MerchantScanFormProps {
  onSubmit: (merchant: MerchantInput) => void
  submitting: boolean
  disabled?: boolean
  disabledReason?: string
}

export function MerchantScanForm({
  onSubmit,
  submitting,
  disabled = false,
  disabledReason,
}: MerchantScanFormProps) {
  const [values, setValues] = useState<MerchantInput>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})

  function set(field: keyof MerchantInput, value: string) {
    setValues((v) => ({ ...v, [field]: value }))
    setErrors((e) => (e[field] ? { ...e, [field]: undefined } : e))
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const found = validate(values)
    setErrors(found)
    if (Object.keys(found).length > 0) return
    onSubmit({
      ...values,
      website_url: normaliseUrl(values.website_url),
      business_type: values.business_type?.trim() ? values.business_type : undefined,
    })
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Card>
        <CardHeader
          title="Merchant website"
          subtitle="The engine crawls up to 20 pages, then audits what it finds."
        />
        <Input
          label="Website URL"
          placeholder="artisanweaves.in"
          value={values.website_url}
          onChange={(e) => set('website_url', e.target.value)}
          error={errors.website_url}
          mono
          autoComplete="url"
        />
      </Card>

      <Card>
        <CardHeader
          title="KYC documents"
          subtitle="Enter each name exactly as it appears on the document. Differences are the point."
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Name on PAN"
            placeholder="Artisan Weaves Private Limited"
            value={values.pan_name}
            onChange={(e) => set('pan_name', e.target.value)}
            error={errors.pan_name}
          />
          <Input
            label="GST legal name"
            placeholder="ARTISAN WEAVES PRIVATE LIMITED"
            value={values.gst_legal_name}
            onChange={(e) => set('gst_legal_name', e.target.value)}
            error={errors.gst_legal_name}
          />
          <Input
            label="Bank account name"
            placeholder="Artisan Weaves Private Limited"
            value={values.bank_account_name}
            onChange={(e) => set('bank_account_name', e.target.value)}
            error={errors.bank_account_name}
          />
          <Select
            label="Business type"
            value={values.business_type ?? ''}
            onChange={(e) => set('business_type', e.target.value)}
            hint="Changes which policy checklist variant applies"
          >
            {BUSINESS_TYPES.map((b) => (
              <option key={b.value} value={b.value}>
                {b.label}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-caption text-text-tertiary">Load a test site:</span>
          {DEMO_SITES.map((site) => (
            <Button
              key={site.key}
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setValues({ ...site.merchant, business_type: site.merchant.business_type ?? '' })
                setErrors({})
              }}
            >
              {site.label}
              <span className="text-text-tertiary">
                {site.expected} {site.grade}
              </span>
            </Button>
          ))}
        </div>

        <Button
          type="submit"
          size="lg"
          loading={submitting}
          disabled={disabled}
          leadingIcon={<Radar className="h-4 w-4" />}
        >
          Run compliance scan
        </Button>
      </div>

      {disabled && disabledReason && (
        <p className="text-right text-caption text-status-danger">{disabledReason}</p>
      )}
    </form>
  )
}
