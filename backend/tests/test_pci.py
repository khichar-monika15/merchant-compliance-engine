from backend.agents import kyc_validator, pci_scanner
from backend.agents.pci_scanner import _score_headers, _score_scripts
from backend.tools.csp_parser import analyze_security_headers, grade_csp, parse_csp
from backend.tools.script_analyzer import extract_scripts, score_script_risk

_PERFECT_HEADERS = {
    "content-security-policy": "default-src 'none'; script-src 'self'; object-src 'none'",
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}


class TestCSPParser:
    def test_parse_empty(self):
        result = parse_csp("")
        assert result == {}

    def test_parse_basic(self):
        result = parse_csp("default-src 'self'; script-src 'self' https://cdn.example.com")
        assert "default-src" in result
        assert "script-src" in result
        assert "'self'" in result["default-src"]

    def test_grade_no_csp(self):
        result = grade_csp({})
        assert result["present"] is False
        assert result["score"] == 0

    def test_grade_unsafe_inline(self):
        parsed = parse_csp("default-src 'self'; script-src 'unsafe-inline'")
        result = grade_csp(parsed)
        assert result["score"] < 80
        assert any("unsafe-inline" in issue for issue in result["issues"])

    def test_grade_strong_csp(self):
        parsed = parse_csp(
            "default-src 'none'; script-src 'self'; "
            "object-src 'none'; upgrade-insecure-requests"
        )
        result = grade_csp(parsed)
        assert result["strength"] in ("strong", "moderate")


class TestSecurityHeaders:
    def test_missing_all_headers(self):
        result = analyze_security_headers({})
        assert result["hsts"]["present"] is False
        assert result["x_frame_options"]["present"] is False
        assert result["csp"]["present"] is False

    def test_full_security_headers(self):
        headers = {
            "content-security-policy": "default-src 'self'; object-src 'none'",
            "strict-transport-security": "max-age=31536000; includeSubDomains",
            "x-frame-options": "DENY",
            "x-content-type-options": "nosniff",
            "referrer-policy": "strict-origin-when-cross-origin",
        }
        result = analyze_security_headers(headers)
        assert result["hsts"]["present"] is True
        assert result["x_frame_options"]["present"] is True
        assert result["x_content_type"]["present"] is True


class TestScriptAnalyzer:
    SAMPLE_HTML = """
    <html><head>
    <script src="https://www.google-analytics.com/analytics.js"></script>
    <script src="https://cdn.shopify.com/theme.js"
            integrity="sha384-abcdef" crossorigin="anonymous"></script>
    <script>console.log('inline');</script>
    </head></html>
    """

    def test_extract_scripts(self):
        scripts = extract_scripts(self.SAMPLE_HTML, "https://myshop.myshopify.com")
        assert len(scripts) == 3

    def test_inline_script_detected(self):
        scripts = extract_scripts(self.SAMPLE_HTML, "https://myshop.myshopify.com")
        inline = [s for s in scripts if s.get("is_inline")]
        assert len(inline) == 1

    def test_sri_detected(self):
        scripts = extract_scripts(self.SAMPLE_HTML, "https://myshop.myshopify.com")
        with_sri = [s for s in scripts if s.get("has_sri")]
        assert len(with_sri) == 1
        assert with_sri[0]["sri_hash"] == "sha384-abcdef"

    def test_third_party_classified(self):
        scripts = extract_scripts(self.SAMPLE_HTML, "https://myshop.myshopify.com")
        ga_script = next(s for s in scripts if "google-analytics" in (s.get("src") or ""))
        assert ga_script["is_first_party"] is False

    def test_risk_scoring_low(self):
        risk_db = {"low_risk": [{"domains": ["google-analytics.com"], "category": "analytics"}], "medium_risk": [], "high_risk_indicators": []}
        result = score_script_risk("www.google-analytics.com", risk_db)
        assert result["risk_level"] == "low"

    def test_risk_scoring_medium(self):
        risk_db = {"low_risk": [], "medium_risk": [{"domains": ["hotjar.com"], "category": "analytics"}], "high_risk_indicators": []}
        result = score_script_risk("static.hotjar.com", risk_db)
        assert result["risk_level"] == "medium"


class TestPCIScoring:
    """PCI-001/002 score out of 50 (scripts), PCI-004/005 out of 50 (headers) — 100 total."""

    def test_perfect_site_scores_100(self):
        header_score, header_issues = _score_headers(analyze_security_headers(_PERFECT_HEADERS))
        script_score, script_issues = _score_scripts(third_party_count=0, without_sri=0)
        assert header_score + script_score == 100
        assert header_issues == []
        assert script_issues == []

    def test_missing_referrer_policy_costs_6(self):
        headers = {k: v for k, v in _PERFECT_HEADERS.items() if k != "referrer-policy"}
        score, issues = _score_headers(analyze_security_headers(headers))
        assert score == 44
        assert any("Referrer-Policy" in i for i in issues)

    def test_missing_csp_costs_20(self):
        headers = {k: v for k, v in _PERFECT_HEADERS.items() if k != "content-security-policy"}
        score, issues = _score_headers(analyze_security_headers(headers))
        assert score == 30
        assert any("CSP" in i for i in issues)

    def test_no_headers_at_all(self):
        score, issues = _score_headers(analyze_security_headers({}))
        assert score == 5  # 50 - 20 CSP - 7 HSTS - 6 XFO - 6 XCTO - 6 RP
        assert len(issues) == 5

    def test_scripts_without_sri_deducted_per_script(self):
        score, issues = _score_scripts(third_party_count=4, without_sri=4)
        assert score == 38  # 50 - (3 * 4)
        assert any("SRI" in i for i in issues)

    def test_script_deduction_is_capped(self):
        score, _ = _score_scripts(third_party_count=30, without_sri=30)
        assert score == 10  # 50 - 15 (count) - 25 (SRI cap)


class TestAgentRunContract:
    """Every agent returns a partial state update whose keys exist on EngineState."""

    async def test_pci_scanner_run(self, basic_engine_state, crawl_result_no_policies):
        basic_engine_state.crawl_result = crawl_result_no_policies
        update = await pci_scanner.run(basic_engine_state)

        assert set(update) <= set(type(basic_engine_state).model_fields)
        result = update["pci_result"]
        assert 0 <= result.security_score <= 100
        assert result.third_party_scripts == 3
        assert result.scripts_without_sri == 3
        assert update["audit_log"][-1].agent == "PCIScanner"

    async def test_pci_scanner_without_crawl_degrades(self, basic_engine_state):
        """A missing crawl must produce an error entry, not raise."""
        update = await pci_scanner.run(basic_engine_state)
        assert "errors" in update
        assert update["audit_log"][-1].agent == "PCIScanner"

    async def test_kyc_validator_run(self, basic_engine_state):
        update = await kyc_validator.run(basic_engine_state)

        assert set(update) <= set(type(basic_engine_state).model_fields)
        # The FreshKart fixture has Pvt./Private and spacing differences planted
        assert update["kyc_result"].overall_consistent is False
        assert update["audit_log"][-1].agent == "KYCValidator"
