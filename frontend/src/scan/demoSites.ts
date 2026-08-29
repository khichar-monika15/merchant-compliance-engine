import type { MerchantInput } from '@/api/types'

export interface DemoSite {
  key: string
  label: string
  expected: string
  grade: string
  merchant: MerchantInput
}

/**
 * The four synthetic test sites, with the exact KYC names the ground-truth fixtures use so a
 * demo run reproduces the published score. Serve them on 4001 to 4004 first.
 */
export const DEMO_SITES: DemoSite[] = [
  {
    key: 'freshkart',
    label: 'FreshKart India',
    expected: '19',
    grade: 'F',
    merchant: {
      website_url: 'http://127.0.0.1:4001',
      pan_name: 'FreshKart Pvt. Ltd.',
      gst_legal_name: 'FRESHKART PRIVATE LIMITED',
      bank_account_name: 'Fresh Kart Private Limited',
      business_type: 'ecommerce',
    },
  },
  {
    key: 'quickbites',
    label: 'QuickBites Delivery',
    expected: '28',
    grade: 'D',
    merchant: {
      website_url: 'http://127.0.0.1:4002',
      pan_name: 'QuickBites Pvt. Ltd.',
      gst_legal_name: 'QUICKBITES PRIVATE LIMITED',
      bank_account_name: 'Quick Bites Private Limited',
      business_type: 'food_delivery',
    },
  },
  {
    key: 'clouddesk',
    label: 'CloudDesk SaaS',
    expected: '55',
    grade: 'C',
    merchant: {
      website_url: 'http://127.0.0.1:4003',
      pan_name: 'CloudDesk Solutions Private Limited',
      gst_legal_name: 'CLOUDDESK SOLUTIONS PRIVATE LIMITED',
      bank_account_name: 'CloudDesk Solutions Private Limited',
      business_type: 'saas',
    },
  },
  {
    key: 'artisan',
    label: 'Artisan Weaves',
    expected: '81',
    grade: 'B',
    merchant: {
      website_url: 'http://127.0.0.1:4004',
      pan_name: 'Artisan Weaves Private Limited',
      gst_legal_name: 'ARTISAN WEAVES PRIVATE LIMITED',
      bank_account_name: 'Artisan Weaves Private Limited',
      business_type: 'ecommerce',
    },
  },
]
