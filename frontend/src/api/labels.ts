/**
 * Human labels for the identifiers the engine uses internally.
 *
 * `food_delivery` and `vue_nuxt` are keys in the knowledge base, not words for a merchant to
 * read. The scan form already had labels for business types; keeping them there meant the report
 * rendered the raw key next to the merchant's own name.
 *
 * Anything without an explicit label falls back to a readable form rather than showing an
 * underscore, so a new key added to the knowledge base degrades to "Food delivery" rather than
 * to nothing. `test_frontend_claims.py` fails the build when a declared key has no label here,
 * so the fallback is a safety net and not the plan.
 */

export const BUSINESS_TYPE_LABELS: Record<string, string> = {
  ecommerce: 'E-commerce',
  saas: 'SaaS',
  services: 'Services',
  food_delivery: 'Food delivery',
}

export const STACK_LABELS: Record<string, string> = {
  shopify: 'Shopify',
  woocommerce: 'WooCommerce',
  wordpress: 'WordPress',
  nextjs: 'Next.js',
  react: 'React',
  vue_nuxt: 'Vue / Nuxt',
  django: 'Django',
  laravel: 'Laravel',
  static_html: 'Static HTML',
}

/** `food_delivery` -> `Food delivery`. The last resort, not the usual path. */
export function humanise(value: string): string {
  const spaced = value.replace(/[_-]+/g, ' ').trim()
  return spaced ? spaced[0].toUpperCase() + spaced.slice(1) : ''
}

export function businessTypeLabel(value: string | null | undefined): string {
  if (!value) return ''
  return BUSINESS_TYPE_LABELS[value] ?? humanise(value)
}

export function stackLabel(value: string | null | undefined): string {
  if (!value) return ''
  return STACK_LABELS[value] ?? humanise(value)
}

/**
 * How a merchant integrates Razorpay. Declared per stack as `integration_method` in
 * `tech_stack_signatures.json`, and it was rendering as `standard_checkout` under the product
 * name. Every declared method is checked against this map by `test_frontend_claims.py`.
 */
export const INTEGRATION_METHOD_LABELS: Record<string, string> = {
  standard_checkout: 'Standard Checkout',
  payment_button: 'Payment Button',
  shopify_app: 'Shopify app',
  woocommerce_plugin: 'WooCommerce plugin',
}

export function integrationMethodLabel(value: string | null | undefined): string {
  if (!value) return ''
  return INTEGRATION_METHOD_LABELS[value] ?? humanise(value)
}
