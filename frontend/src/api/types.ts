// Types derived from backend/models/schemas.py — keep in sync

export type Severity = 'critical' | 'warning' | 'info' | 'pass'

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
  business_category?: string
  overall_score: number
}

// --- PCI DSS ---
export interface SecurityHeaderInfo {
  present: boolean
  value?: string
  strength?: string
  score?: number
  issues?: string[]
  directives?: Record<string, string[]>
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
  critical_issues: string[]
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
  info_items: GapItem[]
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
