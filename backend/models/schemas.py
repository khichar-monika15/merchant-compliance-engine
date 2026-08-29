from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, HttpUrl, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    PASS = "pass"


class MerchantInput(BaseModel):
    website_url: HttpUrl
    pan_name: str
    gst_legal_name: str
    bank_account_name: str
    business_type: Optional[str] = None


class ScriptInfo(BaseModel):
    src: Optional[str] = None
    domain: Optional[str] = None
    has_sri: bool = False
    sri_hash: Optional[str] = None
    is_inline: bool = False
    is_first_party: bool = False
    risk_level: Optional[str] = None  # low / medium / high
    category: Optional[str] = None    # analytics / ad-tech / chat / social / unknown


class CrawlResult(BaseModel):
    pages_found: dict[str, str] = {}          # {url: html_content}
    scripts_found: list[ScriptInfo] = []
    http_headers: dict[str, dict] = {}         # {url: {header: value}}
    navigation_links: list[str] = []
    identified_pages: dict[str, str] = {}      # {type: url}
    tech_stack_signals: dict[str, list[str]] = {}
    crawl_errors: list[str] = []
    pages_crawled: int = 0
    crawl_duration_seconds: float = 0.0


class ComplianceCheck(BaseModel):
    name: str
    check_id: str
    found: bool = False
    url: Optional[str] = None
    quality_score: int = 0           # 0-10
    severity: Severity = Severity.CRITICAL
    issues: list[str] = []
    details: Optional[str] = None


class ComplianceResult(BaseModel):
    refund_policy: ComplianceCheck = Field(
        default_factory=lambda: ComplianceCheck(name="Refund Policy", check_id="RBI-001")
    )
    privacy_policy: ComplianceCheck = Field(
        default_factory=lambda: ComplianceCheck(name="Privacy Policy", check_id="RBI-002")
    )
    terms_conditions: ComplianceCheck = Field(
        default_factory=lambda: ComplianceCheck(name="Terms & Conditions", check_id="RBI-003")
    )
    contact_info: ComplianceCheck = Field(
        default_factory=lambda: ComplianceCheck(name="Contact Information", check_id="RBI-004")
    )
    gst_display: ComplianceCheck = Field(
        default_factory=lambda: ComplianceCheck(
            name="GST Display", check_id="RBI-005", severity=Severity.WARNING
        )
    )
    business_category: Optional[str] = None
    overall_score: int = 0


class PCIIssue(BaseModel):
    """A PCI finding tagged with the check that produced it.

    The severity used to be guessed in the report generator by substring-matching the message
    text for "csp", "sri" and "6.4.3", under a comment claiming it followed the knowledge base.
    Carrying the check id means the declared severity is the one that gets used.
    """

    check_id: str
    message: str
    severity: Severity


class PCIResult(BaseModel):
    scripts_inventory: list[ScriptInfo] = []
    total_scripts: int = 0
    third_party_scripts: int = 0
    scripts_without_sri: int = 0
    csp_header: dict = {}
    hsts_header: dict = {}
    x_frame_options: dict = {}
    x_content_type: dict = {}
    referrer_policy: dict = {}
    security_score: int = 0
    issues: list[PCIIssue] = []
    # The message text of `issues`, kept so the report renders a plain list. Derived, not a
    # second source of truth.
    critical_issues: list[str] = []


class KYCMatch(BaseModel):
    match: bool = False
    similarity: float = 0.0
    normalized_a: str = ""
    normalized_b: str = ""
    issues: list[str] = []


class KYCResult(BaseModel):
    pan_gst_match: KYCMatch = Field(default_factory=KYCMatch)
    gst_bank_match: KYCMatch = Field(default_factory=KYCMatch)
    pan_bank_match: KYCMatch = Field(default_factory=KYCMatch)
    common_mismatches: list[str] = []
    overall_consistent: bool = False
    confidence: float = 0.0


class GeneratedPolicy(BaseModel):
    policy_type: str
    content: str
    tailored_to: str
    word_count: int = 0


class PolicyGenResult(BaseModel):
    generated_policies: list[GeneratedPolicy] = []
    policies_needed: list[str] = []


class IntegrationResult(BaseModel):
    detected_stack: dict = {}
    recommended_product: str = ""
    # Why this product, and where to read about it. Both are declared per stack in
    # tech_stack_signatures.json and used to be dropped here, so the merchant was told what to
    # integrate but never why or where the documentation was.
    recommendation_reason: str = ""
    docs_url: str = ""
    integration_method: str = ""
    starter_code: str = ""
    starter_code_language: str = ""
    test_payment_result: dict = {}


class GapItem(BaseModel):
    title: str
    description: str
    severity: Severity
    category: str
    fix_suggestion: str = ""


class AuditLogEntry(BaseModel):
    timestamp: str
    agent: str
    action: str
    result: str
    duration_ms: Optional[float] = None


class ScoreComponent(BaseModel):
    """One weighted axis of the readiness score, as the backend actually computed it."""
    label: str
    score: int  # 0-100
    weight: float  # fraction of the overall score


class ReadinessReport(BaseModel):
    overall_score: int = 0
    grade: str = "F"
    score_breakdown: list[ScoreComponent] = []
    critical_gaps: list[GapItem] = []
    warnings: list[GapItem] = []
    info_items: list[GapItem] = []
    compliance_details: Optional[ComplianceResult] = None
    pci_details: Optional[PCIResult] = None
    kyc_details: Optional[KYCResult] = None
    generated_policies: Optional[PolicyGenResult] = None
    integration_details: Optional[IntegrationResult] = None
    estimated_fix_time: str = ""
    audit_trail: list[AuditLogEntry] = []


class EngineState(BaseModel):
    merchant_input: MerchantInput
    crawl_result: Optional[CrawlResult] = None
    compliance_result: Optional[ComplianceResult] = None
    pci_result: Optional[PCIResult] = None
    kyc_result: Optional[KYCResult] = None
    policy_gen_result: Optional[PolicyGenResult] = None
    integration_result: Optional[IntegrationResult] = None
    readiness_report: Optional[ReadinessReport] = None
    current_phase: str = "init"
    errors: list[str] = []
    audit_log: list[AuditLogEntry] = []


# API models
class ScanRequest(BaseModel):
    website_url: HttpUrl
    pan_name: str
    gst_legal_name: str
    bank_account_name: str
    business_type: Optional[str] = None


class ScanResponse(BaseModel):
    job_id: str
    status: str
    report: Optional[ReadinessReport] = None
    # Why a scan failed. Without this the reason existed only in the WebSocket stream, so a
    # reload turned "could not reach the site" into a bare "failed".
    error: Optional[str] = None
