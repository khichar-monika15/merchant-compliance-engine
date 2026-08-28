import { useState, FormEvent } from 'react'
import { MerchantInput } from '../types'

interface Props {
  onSubmit: (merchant: MerchantInput) => void
  disabled?: boolean
}

export function InputForm({ onSubmit, disabled }: Props) {
  const [form, setForm] = useState<MerchantInput>({
    website_url: '',
    pan_name: '',
    gst_legal_name: '',
    bank_account_name: '',
    business_type: '',
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit({
      website_url: form.website_url.trim(),
      pan_name: form.pan_name.trim(),
      gst_legal_name: form.gst_legal_name.trim(),
      bank_account_name: form.bank_account_name.trim(),
      business_type: form.business_type?.trim() || undefined,
    })
  }

  const field = (
    key: keyof MerchantInput,
    label: string,
    placeholder: string,
    required = false,
  ) => (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <input
        type="text"
        value={form[key] ?? ''}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        required={required}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  )

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {field('website_url', 'Merchant Website URL', 'https://example.com', true)}
      {field('pan_name', 'PAN Card / Business Name (as on PAN)', 'Acme Private Limited', true)}
      {field('gst_legal_name', 'GST Legal Name (as on GST certificate)', 'ACME PRIVATE LIMITED', true)}
      {field('bank_account_name', 'Bank Account Name (as on bank statement)', 'Acme Private Limited', true)}
      {field('business_type', 'Business Type (optional)', 'ecommerce / saas / food_delivery / services')}
      <button
        type="submit"
        disabled={disabled}
        className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {disabled ? 'Scanning...' : 'Run Compliance Scan'}
      </button>
    </form>
  )
}
