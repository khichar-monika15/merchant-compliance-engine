import pytest

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
        # The message is the analyser's, not a second copy kept in the scorer.
        assert any(cid == "PCI-005" and msg.startswith("Referrer-Policy missing") for cid, msg in issues)

    def test_missing_csp_costs_20(self):
        headers = {k: v for k, v in _PERFECT_HEADERS.items() if k != "content-security-policy"}
        score, issues = _score_headers(analyze_security_headers(headers))
        assert score == 30
        assert any(cid == "PCI-004" and "CSP" in msg for cid, msg in issues)

    def test_no_headers_at_all(self):
        score, issues = _score_headers(analyze_security_headers({}))
        assert score == 5  # 50 - 20 CSP - 7 HSTS - 6 XFO - 6 XCTO - 6 RP
        assert len(issues) == 5

    def test_scripts_without_sri_deducted_per_script(self):
        score, issues = _score_scripts(third_party_count=4, without_sri=4)
        assert score == 38  # 50 - (3 * 4)
        # The check id matters: SRI is PCI-002, and its severity drives the gap in the report.
        assert any(cid == "PCI-002" and "SRI" in msg for cid, msg in issues)

    def test_script_deduction_is_capped(self):
        score, _ = _score_scripts(third_party_count=30, without_sri=30)
        assert score == 10  # 50 - 15 (count) - 25 (SRI cap)


class TestFirstPartyClassification:
    """A merchant's own scripts must not count against its PCI score."""

    SITE = "https://www.example.com/checkout"

    def test_apex_script_on_www_site_is_first_party(self):
        scripts = extract_scripts('<script src="https://example.com/app.js"></script>', self.SITE)
        assert scripts[0]["is_first_party"] is True

    def test_www_script_on_apex_site_is_first_party(self):
        scripts = extract_scripts('<script src="https://www.example.com/app.js"></script>', "https://example.com/")
        assert scripts[0]["is_first_party"] is True

    def test_subdomain_is_first_party(self):
        scripts = extract_scripts('<script src="https://cdn.example.com/app.js"></script>', self.SITE)
        assert scripts[0]["is_first_party"] is True

    def test_genuine_third_party_still_detected(self):
        scripts = extract_scripts('<script src="https://evil-example.com/x.js"></script>', self.SITE)
        assert scripts[0]["is_first_party"] is False

    def test_lookalike_suffix_is_not_first_party(self):
        scripts = extract_scripts('<script src="https://notexample.com/x.js"></script>', self.SITE)
        assert scripts[0]["is_first_party"] is False


class TestHeaderPageSelection:
    from backend.models.schemas import CrawlResult as _CR

    def test_prefers_checkout_page_over_first_crawled(self):
        from backend.agents.pci_scanner import _headers_to_grade

        crawl = self._CR(http_headers={
            "https://shop.in/privacy": {"x-frame-options": "DENY"},
            "https://shop.in/checkout": {"content-security-policy": "default-src 'self'"},
        })
        url, headers = _headers_to_grade(crawl, "https://shop.in")
        assert url.endswith("/checkout")
        assert "content-security-policy" in headers

    def test_falls_back_to_homepage(self):
        from backend.agents.pci_scanner import _headers_to_grade

        crawl = self._CR(http_headers={
            "https://shop.in/privacy": {"x-frame-options": "DENY"},
            "https://shop.in": {"strict-transport-security": "max-age=31536000"},
        })
        url, headers = _headers_to_grade(crawl, "https://shop.in")
        assert url == "https://shop.in"

    def test_no_headers_at_all(self):
        from backend.agents.pci_scanner import _headers_to_grade

        assert _headers_to_grade(self._CR(), "https://shop.in") == ("", {})


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


class TestRiskCategoriesAreReachable:
    """A category declared in the risk database that no domain can produce is an inert rule.

    Matching was first-wins over `endswith`, so `googleapis.com` (category "google") shadowed
    `fonts.googleapis.com` (category "fonts") and the fonts category could never be emitted.
    """

    def test_every_declared_category_can_be_produced(self):
        from backend.tools.script_analyzer import _load_risk_db, score_script_risk

        db = _load_risk_db()
        declared, produced = set(), set()
        for level in ("low_risk", "medium_risk"):
            for entry in db[level]:
                declared.add(entry["category"])
                for domain in entry["domains"]:
                    produced.add(score_script_risk(domain, db)["category"])

        unreachable = sorted(declared - produced)
        assert not unreachable, (
            f"categories the database declares that no declared domain produces: {unreachable}"
        )

    def test_the_most_specific_domain_wins(self):
        from backend.tools.script_analyzer import _load_risk_db, score_script_risk

        db = _load_risk_db()
        assert score_script_risk("fonts.googleapis.com", db)["category"] == "fonts"
        assert score_script_risk("googleapis.com", db)["category"] == "google"


class TestDeclaredHeaderRequirementsAreApplied:
    """PCI-005 declares a `requirement` per header. Presence alone used to earn the points.

    The parser computed every one of these shortfalls and the scorer read only `present`, so a
    site could send `max-age=1` or `Referrer-Policy: unsafe-url` and score as if it were correctly
    configured. Parsed is not applied.
    """

    def _present_but_wrong(self, header: str, value: str) -> tuple[int, list]:
        headers = {**_PERFECT_HEADERS, header: value}
        return _score_headers(analyze_security_headers(headers))

    def test_hsts_below_the_declared_max_age_loses_its_points(self):
        score, issues = self._present_but_wrong("strict-transport-security", "max-age=1")
        assert score == 43, "a one second HSTS max-age scored as a compliant header"
        assert any(cid == "PCI-005" and "max-age" in msg for cid, msg in issues), issues

    def test_x_frame_options_off_the_declared_values_loses_its_points(self):
        score, issues = self._present_but_wrong(
            "x-frame-options", "ALLOW-FROM https://evil.example"
        )
        assert score == 44
        assert any(cid == "PCI-005" and "X-Frame-Options" in msg for cid, msg in issues), issues

    def test_x_content_type_wrong_value_loses_its_points(self):
        score, issues = self._present_but_wrong("x-content-type-options", "sniff")
        assert score == 44
        assert any(cid == "PCI-005" and "X-Content-Type" in msg for cid, msg in issues), issues

    def test_referrer_policy_that_leaks_the_url_loses_its_points(self):
        score, issues = self._present_but_wrong("referrer-policy", "unsafe-url")
        assert score == 44
        assert any(cid == "PCI-005" and "Referrer-Policy" in msg for cid, msg in issues), issues

    def test_a_genuinely_safe_referrer_policy_still_scores(self):
        """The declared requirement has to accept the values a careful merchant actually sends.

        Artisan Weaves sends `strict-origin-when-cross-origin`, which is stronger than the two
        values PCI-005 originally named. A requirement too narrow to accept a correct header is
        the same defect in the other direction.
        """
        for safe in ("strict-origin-when-cross-origin", "no-referrer", "same-origin", "origin"):
            score, issues = self._present_but_wrong("referrer-policy", safe)
            assert score == 50, f"{safe} was penalised: {issues}"

    def test_every_declared_requirement_is_applied_by_the_scorer(self):
        """No header may reach the scorer without its declared requirement being enforced."""
        from backend.agents.pci_scanner import _HEADER_RULES

        declared = {h["name"] for h in pci_scanner._HEADER_SUITE["headers"]}
        wired = {name for name, _, _ in _HEADER_RULES}
        assert declared == wired, f"declared but never scored: {sorted(declared - wired)}"


@pytest.mark.parametrize(
    "header",
    pci_scanner._HEADER_SUITE["headers"],
    ids=lambda h: h["name"],
)
class TestEveryDeclaredHeaderCostsItsDeclaredPoints:
    """Driven from the checklist, so adding a header there forces it to be scored.

    This is the guard that would have caught the requirement bug. The textual guard in
    `test_no_inert_declarations.py` cannot: PCI-001 and PCI-005 both declare a key called
    `requirement` in the same module, so one satisfied the other's read. Asserting on behaviour
    rather than on the presence of a subscript is the only thing that separates them.
    """

    @staticmethod
    def _header_key(name: str) -> str:
        return name.lower()

    def test_absent_header_costs_exactly_its_declared_points(self, header):
        headers = {k: v for k, v in _PERFECT_HEADERS.items() if k != self._header_key(header["name"])}
        score, _ = _score_headers(analyze_security_headers(headers))
        assert score == 50 - header["points"], (
            f"{header['name']} is declared as {header['points']} points"
        )

    def test_a_value_failing_the_requirement_costs_the_same(self, header):
        # A value chosen to fail whatever the checklist declares for this header.
        bad = "max-age=1" if "max-age" in header["requirement"] else "definitely-not-a-valid-value"
        headers = {**_PERFECT_HEADERS, self._header_key(header["name"]): bad}
        score, issues = _score_headers(analyze_security_headers(headers))

        assert score == 50 - header["points"], (
            f"{header['name']}: {header['requirement']!r} is declared and was not applied. "
            f"A header sending {bad!r} scored as if it were compliant."
        )
        assert any(header["name"] in msg for _, msg in issues), issues
