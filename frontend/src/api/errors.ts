import axios from 'axios'

/**
 * Surface FastAPI's validation detail instead of a bare "status code 422".
 *
 * `website_url` is a Pydantic HttpUrl, so a merchant typed as `example.com` without a scheme is
 * the single most likely error in the app. This is the only thing that renders it as words.
 */
export function describeError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => `${d.loc?.slice(1).join('.') ?? 'field'}: ${d.msg}`).join('; ')
    }
    if (!err.response) {
      return 'Could not reach the compliance engine. Check that the backend is running on port 8000.'
    }
  }
  return err instanceof Error ? err.message : 'Scan failed'
}
