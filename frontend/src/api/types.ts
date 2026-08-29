// Types derived from backend/models/schemas.py, keep in sync

export type Severity = 'critical' | 'warning'

// --- Merchant input (matches backend MerchantInput + ScanRequest) ---
export interface MerchantInput {
  website_url: string
  pan_name: string
  gst_legal_name: string
  bank_account_name: string
  business_type?: string
}

// --- Crawl / Scripts ---
export interface ScriptInfo {
  src?: string
  domain?: string
  has_sri: boolean
  sri_hash?: string
  is_inline: boolean
  is_first_party: boolean
  risk_level?: 'low' | 'medium' | 'high'
  category?: string
}

// --- Compliance (RBI) ---
export interface ComplianceCheck {
  name: string
  check_id: string
  found: boolean
  url?: string
  quality_score: number
  severity: Severity
  issues: string[]
  details?: string
}

export interface ComplianceResult {
  refund_policy: ComplianceCheck
  privacy_policy: ComplianceCheck
  terms_conditions: ComplianceCheck
  contact_info: ComplianceCheck
  gst_display: ComplianceCheck
  /** RBI-007. Null for merchants that deliver nothing physical, where the check does not apply. */
  shipping_policy?: ComplianceCheck | null
  business_category?: string
  overall_score: number
}

// --- PCI DSS ---
export interface SecurityHeaderInfo {
  present: boolean
  /** The raw header value. Absent on the CSP result, which carries `directives` instead. */
  value?: string
  /** CSP only: the parsed policy, its band, and its 0-100 score. */
  directives?: Record<string, string[]>
  strength?: string
  score?: number
  /** Set on the CSP-absent path, where there are no directives to report. */
  policy?: string
  /** Why this header falls short, for example an HSTS max-age below the required minimum. */
  issues?: string[]
}

export interface PCIResult {
  scripts_inventory: ScriptInfo[]
  total_scripts: number
  third_party_scripts: number
  scripts_without_sri: number
  csp_header: SecurityHeaderInfo
  hsts_header: SecurityHeaderInfo
  x_frame_options: SecurityHeaderInfo
  x_content_type: SecurityHeaderInfo
  referrer_policy: SecurityHeaderInfo
  security_score: number
  /** Findings tagged with the check that produced them and that check's declared severity. */
  issues: PCIIssue[]
  /** The message text of `issues`, for a plain list. Derived, not a second source of truth. */
  critical_issues: string[]
}

export interface PCIIssue {
  check_id: string
  message: string
  severity: Severity
}

// --- KYC ---
export interface KYCMatch {
  match: boolean
  similarity: number
  normalized_a: string
  normalized_b: string
  issues: string[]
}

export interface KYCResult {
  pan_gst_match: KYCMatch
  gst_bank_match: KYCMatch
  pan_bank_match: KYCMatch
  common_mismatches: string[]
  overall_consistent: boolean
  confidence: number
}

// --- Policy generation ---
export interface GeneratedPolicy {
  policy_type: string
  content: string
  tailored_to: string
  word_count: number
}

export interface PolicyGenResult {
  generated_policies: GeneratedPolicy[]
  policies_needed: string[]
}

// --- Integration ---
export interface IntegrationResult {
  detected_stack: Record<string, string[]>
  recommended_product: string
  /** Why this product, and where its docs are. Declared per stack in the knowledge base. */
  recommendation_reason: string
  docs_url: string
  integration_method: string
  starter_code: string
  starter_code_language: string
  test_payment_result: Record<string, unknown>
}

// --- Gaps ---
export interface GapItem {
  title: string
  description: string
  severity: Severity
  category: string
  fix_suggestion: string
  /** The page the finding came from, where the check found one. */
  source_url?: string | null
}

// --- Audit ---
export interface AuditLogEntry {
  timestamp: string
  agent: string
  action: string
  result: string
  duration_ms?: number
}

// --- Final report (matches backend ReadinessReport) ---
export interface ReadinessReport {
  overall_score: number
  grade: string
  score_breakdown: ScoreComponent[]
  critical_gaps: GapItem[]
  warnings: GapItem[]
  compliance_details?: ComplianceResult
  pci_details?: PCIResult
  kyc_details?: KYCResult
  generated_policies?: PolicyGenResult
  integration_details?: IntegrationResult
  estimated_fix_time: string
  audit_trail: AuditLogEntry[]
}

// --- API ---
export type ScanStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface ScanResponse {
  job_id: string
  status: ScanStatus
  report?: ReadinessReport | null
  /** Why a failed scan failed. Null on every other status. */
  error?: string | null
}

export interface ScoreComponent {
  label: string
  score: number
  weight: number
}

export type ProgressEvent = {
  type: 'progress' | 'complete' | 'error' | 'ping'
  agent?: string
  message?: string
  progress?: number
  done?: boolean
  timestamp?: string
}

// --- Knowledge base (GET /api/knowledge) ---
export interface RbiCheck {
  id: string
  category: string
  name: string
  severity: Severity
  description: string
  detection_strategy: string
  search?: {
    url_patterns?: string[]
    link_text_patterns?: string[]
    footer_patterns?: string[]
    body_keywords?: string[]
  }
  quality_criteria?: {
    min_word_count?: number
    must_contain_topics?: string[]
    red_flags?: string[]
    required_elements?: Record<
      string,
      {
        pin_code_pattern?: string
        locality_keywords?: string[]
        candidate_pattern?: string
        subscriber_digits?: number
        allowed_leading_digits?: string
        pattern?: string
        note?: string
      }
    >
    gst_pattern?: string
    normalization_rules?: Array<{ pattern: string; replacement: string; ignore_case?: boolean }>
    known_mismatch_patterns?: string[]
    min_similarity_threshold?: number
  }
  business_type_variations?: Record<string, { extra_topics?: string[] }>
}

export interface PciCheck {
  id: string
  requirement: string
  name: string
  severity: Severity
  description: string
  /** Only PCI-001 uses `deductions`. The other checks each score differently, and the page
   *  renders whichever shape a check actually declares. PCI-003 has no scoring block at all. */
  scoring?: {
    max_points?: number
    deductions?: Array<{ condition: string; points: number; reason: string }>
    per_script_without_sri_deduction?: number
    max_deduction?: number
    no_csp_deduction?: number
    weak_csp_deduction?: number
    moderate_csp_deduction?: number
    strong_csp_deduction?: number
    headers?: Array<{ name: string; points: number; requirement?: string }>
  }
  known_exemptions?: string[]
  notes?: string
  /** PCI-003 raises warnings from the script risk classification without carrying points. */
  findings?: {
    flag_risk_levels: string[]
    elevated_categories: string[]
    elevated_reason: string
  }
  grading?: Record<string, { score_min: number; description: string }>
}

export interface RiskEntry {
  domains: string[]
  category: string
}

export interface StackSignature {
  /** No display name is declared per stack; the object key is the identifier. */
  razorpay_recommendation: {
    product: string
    reason: string
    integration_method: string
    docs_url: string
  }
}

export interface KnowledgeBase {
  rbi: { version: string; source: string; checks: RbiCheck[] }
  pci: { version: string; source: string; checks: PciCheck[]; payment_page_patterns: string[] }
  script_risk: {
    version: string
    last_updated: string
    notes: string
    low_risk: RiskEntry[]
    medium_risk: RiskEntry[]
    high_risk_indicators: string[]
  }
  stacks: Record<string, StackSignature>
  scoring: {
    weights: Record<string, number>
    grades: Array<{ grade: string; min_score: number }>
  }
}
