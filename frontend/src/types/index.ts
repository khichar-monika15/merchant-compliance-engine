export type Severity = 'CRITICAL' | 'WARNING' | 'INFO' | 'PASS'

export interface MerchantInput {
  website_url: string
  legal_name: string
  trade_name?: string
  gstin?: string
  registration_name?: string
}

export interface ComplianceCheck {
  check_id: string
  name: string
  found: boolean
  url?: string
  quality_score?: number
  severity: Severity
  details: string
  recommendation?: string
}

export interface ComplianceResult {
  checks: ComplianceCheck[]
  overall_score: number
  business_category: string
  policy_pages_found: string[]
}

export interface ScriptInfo {
  src: string
  is_third_party: boolean
  has_sri: boolean
  integrity?: string
  risk_level: 'low' | 'medium' | 'high' | 'unknown'
  domain?: string
}

export interface PCIResult {
  script_count: number
  third_party_count: number
  scripts_with_sri: number
  scripts_missing_sri: number
  scripts: ScriptInfo[]
  security_headers: Record<string, string | null>
  csp_score: number
  headers_score: number
  overall_score: number
  checks: ComplianceCheck[]
}

export interface KYCMatch {
  field_a: string
  field_b: string
  similarity: number
  match: boolean
  issues: string[]
}

export interface KYCResult {
  matches: KYCMatch[]
  all_consistent: boolean
  overall_score: number
  details: string
}

export interface GeneratedPolicy {
  policy_type: string
  content: string
  template_used: string
  word_count: number
}

export interface PolicyGenResult {
  policies_generated: GeneratedPolicy[]
  policies_needed: string[]
}

export interface IntegrationResult {
  detected_stack: string
  recommended_product: string
  starter_code: string
  language: string
  integration_score: number
  recommendations: string[]
}

export interface GapItem {
  id: string
  category: 'rbi' | 'pci' | 'kyc'
  severity: Severity
  description: string
  fix_hint: string
  estimated_hours: number
}

export interface AuditLogEntry {
  agent: string
  action: string
  timestamp: string
  result?: string
  duration_ms?: number
}

export interface ReadinessReport {
  job_id: string
  website_url: string
  legal_name: string
  overall_score: number
  grade: string
  rbi_score: number
  kyc_score: number
  pci_score: number
  integration_score: number
  compliance_result?: ComplianceResult
  pci_result?: PCIResult
  kyc_result?: KYCResult
  policy_gen_result?: PolicyGenResult
  integration_result?: IntegrationResult
  gaps: GapItem[]
  audit_log: AuditLogEntry[]
  estimated_fix_hours: number
  created_at: string
}

export interface ScanRequest {
  merchant: MerchantInput
}

export interface ScanResponse {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  message: string
  report?: ReadinessReport
}

export type ProgressEvent = {
  type: 'progress' | 'complete' | 'error'
  agent?: string
  message: string
  timestamp: string
}
