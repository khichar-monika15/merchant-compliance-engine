import { useState, FormEvent } from 'react'
import { MerchantInput } from '../types'

interface Props {
  onSubmit: (merchant: MerchantInput) => void
  disabled?: boolean
}

export function InputForm({ onSubmit, disabled }: Props) {
  const [form, setForm] = useState<MerchantInput>({
    website_url: '',
    legal_name: '',
    trade_name: '',
    gstin: '',
    registration_name: '',
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit({
      website_url: form.website_url.trim(),
      legal_name: form.legal_name.trim(),
      trade_name: form.trade_name?.trim() || undefined,
      gstin: form.gstin?.trim() || undefined,
      registration_name: form.registration_name?.trim() || undefined,
    })
  }

  const field = (key: keyof MerchantInput, label: string, placeholder: string, required = false) => (
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
      {field('legal_name', 'Legal / Registered Company Name', 'Acme Private Limited', true)}
      {field('trade_name', 'Trade / Brand Name (optional)', 'Acme Store')}
      {field('gstin', 'GSTIN (optional)', '29ABCDE1234F1Z5')}
      {field('registration_name', 'KYC / Registration Document Name (optional)', 'ACME PRIVATE LIMITED')}
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
