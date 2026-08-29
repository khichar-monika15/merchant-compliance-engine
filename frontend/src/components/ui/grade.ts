/**
 * Grade to colour, in one place.
 *
 * This map existed three times: ScoreRing, DashboardHome, and an inline chain of conditionals
 * in ChecksPage. They agreed, which is what a fork looks like right up until it does not.
 */
export const GRADE_TEXT: Record<string, string> = {
  A: 'text-grade-a',
  B: 'text-grade-b',
  C: 'text-grade-c',
  D: 'text-grade-d',
  F: 'text-grade-f',
}

/** Falls back to secondary text for a grade the scorer does not produce. */
export function gradeText(grade: string): string {
  return GRADE_TEXT[grade] ?? 'text-text-secondary'
}
