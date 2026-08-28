from __future__ import annotations

import pytest
from pydantic import HttpUrl

from backend.models.schemas import (
    ComplianceCheck,
    ComplianceResult,
    CrawlResult,
    EngineState,
    MerchantInput,
    PCIResult,
    ScriptInfo,
    Severity,
)


@pytest.fixture
def merchant_input_freshkart() -> MerchantInput:
    return MerchantInput(
        website_url=HttpUrl("https://freshkart-test.vercel.app"),
        pan_name="FreshKart Pvt. Ltd.",
        gst_legal_name="FRESHKART PRIVATE LIMITED",
        bank_account_name="Fresh Kart Private Limited",
        business_type="ecommerce",
    )


@pytest.fixture
def merchant_input_artisan() -> MerchantInput:
    return MerchantInput(
        website_url=HttpUrl("https://artisan-weaves-test.vercel.app"),
        pan_name="Artisan Weaves Private Limited",
        gst_legal_name="ARTISAN WEAVES PRIVATE LIMITED",
        bank_account_name="Artisan Weaves Private Limited",
        business_type="ecommerce",
    )


@pytest.fixture
def sample_html_no_policies() -> str:
    return """
    <html><body>
    <h1>FreshKart India</h1>
    <p>Buy fresh produce online</p>
    <nav>
      <a href="/products">Products</a>
      <a href="/cart">Cart</a>
      <a href="/contact">Contact</a>
    </nav>
    <footer><p>© 2024 FreshKart</p></footer>
    <script src="https://www.google-analytics.com/analytics.js"></script>
    <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    </body></html>
    """


@pytest.fixture
def sample_html_with_policies() -> str:
    return """
    <html><body>
    <h1>Artisan Weaves</h1>
    <nav>
      <a href="/refund-policy">Refund Policy</a>
      <a href="/privacy-policy">Privacy Policy</a>
      <a href="/terms-and-conditions">Terms &amp; Conditions</a>
      <a href="/contact-us">Contact Us</a>
    </nav>
    <footer>
      <p>GSTIN: 29ABCDE1234F1Z5</p>
      <p>Artisan Weaves Private Limited, 123 MG Road, Bangalore 560001</p>
      <p>Phone: +91 9876543210 | Email: hello@artisanweaves.in</p>
    </footer>
    <script src="https://cdn.shopify.com/s/files/1/themes/app.js"
            integrity="sha384-abc123" crossorigin="anonymous"></script>
    </body></html>
    """


@pytest.fixture
def basic_engine_state(merchant_input_freshkart) -> EngineState:
    return EngineState(merchant_input=merchant_input_freshkart)


@pytest.fixture
def crawl_result_no_policies() -> CrawlResult:
    return CrawlResult(
        pages_found={
            "https://freshkart-test.vercel.app": "<html><body><h1>FreshKart</h1></body></html>",
            "https://freshkart-test.vercel.app/contact": "<html><body><p>Email: hello@freshkart.in</p></body></html>",
        },
        scripts_found=[
            ScriptInfo(src="https://www.google-analytics.com/analytics.js", domain="www.google-analytics.com",
                       has_sri=False, is_first_party=False, risk_level="low", category="analytics"),
            ScriptInfo(src="https://connect.facebook.net/fbevents.js", domain="connect.facebook.net",
                       has_sri=False, is_first_party=False, risk_level="medium", category="social"),
            ScriptInfo(src="https://cdn.hotjar.com/c/hotjar.js", domain="cdn.hotjar.com",
                       has_sri=False, is_first_party=False, risk_level="medium", category="session-recording"),
        ],
        http_headers={"https://freshkart-test.vercel.app": {}},
        identified_pages={"contact": "https://freshkart-test.vercel.app/contact"},
        pages_crawled=2,
    )
