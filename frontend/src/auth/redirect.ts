/**
 * Only allow same-site paths back through a post-login redirect. `//evil.com` is a valid URL to
 * the browser but starts with a slash, so a naive check would treat it as a local path.
 */
export function safeRedirect(from: unknown): string {
  if (typeof from !== 'string') return '/dashboard'
  if (!from.startsWith('/') || from.startsWith('//')) return '/dashboard'
  if (from === '/login' || from === '/signup') return '/dashboard'
  return from
}
