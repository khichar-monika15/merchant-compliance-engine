/** Join class names, dropping falsy values. Keeps the primitives free of a clsx dependency. */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}
