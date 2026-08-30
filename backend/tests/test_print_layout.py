"""What the report actually looks like on paper.

"Download PDF" is the browser's own print dialog, so the PDF is whatever the print stylesheet
renders. That stylesheet had never been measured, only read, and the printed report was losing
text off the right edge and wasting most of several pages.

These tests render the built frontend at A4's printable width with print media emulated, which
is the same layout Chrome's "Save as PDF" uses, and measure the result.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from backend.models.database import AuditRun, Base  # noqa: E402
from backend.models.schemas import (  # noqa: E402
    AuditLogEntry,
    GapItem,
    GeneratedPolicy,
    IntegrationResult,
    PCIResult,
    PolicyGenResult,
    ReadinessReport,
    ScoreComponent,
    ScriptInfo,
    Severity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST = REPO_ROOT / "frontend" / "dist"

JOB_ID = "print-layout-fixture-0001"

# A4 is 210mm wide and the stylesheet reserves 16mm each side, so the content box is 178mm.
# CSS pixels are 1/96in, and 178mm is 6.9685in.
A4_CONTENT_PX = round(178 * 96 / 25.4)

# Longer than the content box in a monospace font, so a code block that does not wrap runs off
# the paper and Chrome clips it. This is the line the printed report used to cut in half.
LONG_CODE_LINE = (
    "5. Set your store to **Test mode** in the Razorpay app and place a test order with "
    "test card `4111 1111 1111 1111`, any future expiry, any CVV, then check the Dashboard."
)

LONG_GAP_TITLE = (
    "PCI: 1 third-party social script(s) loaded (connect.facebook.net), review whether they "
    "belong on a payment page (PCI 6.4.3)"
)

# The script inventory renders its source column in a `max-w-xs truncate` cell. On screen the
# rest of a long URL is one hover away; on paper it is gone.
LONG_SCRIPT_SRC = (
    "https://cdn.shopify.com/extensions/9f2c11ae/payments-banner-2/assets/checkout-banner.js"
)

# Both the starter code and a drafted policy render in a box capped at 28rem that scrolls. On
# paper there is nothing to scroll, so everything past the cap is simply gone. These markers sit
# well past it, and a printed report has to carry them.
TALL_BODY_LINES = [f"Clause {n}. This clause has to reach the paper." for n in range(1, 60)]
LAST_CODE_LINE = "## What to check before going live"
LAST_POLICY_LINE = "Clause 59. This clause has to reach the paper."


def _fixture_report() -> ReadinessReport:
    return ReadinessReport(
        overall_score=86,
        grade="B",
        score_breakdown=[
            ScoreComponent(label="RBI Compliance", score=90, weight=0.40),
            ScoreComponent(label="KYC Consistency", score=100, weight=0.25),
            ScoreComponent(label="PCI DSS", score=77, weight=0.20),
            ScoreComponent(label="Integration", score=70, weight=0.15),
        ],
        critical_gaps=[
            GapItem(
                title=LONG_GAP_TITLE,
                description="A social pixel on a payment page widens the cardholder data scope.",
                severity=Severity.CRITICAL,
                category="pci",
                fix_suggestion="Remove the pixel from checkout, or justify it in the inventory.",
                source_url="http://127.0.0.1:4004/",
            ),
        ],
        pci_details=PCIResult(
            scripts_inventory=[
                # No domain, so the inventory falls back to the full src. That is the cell the
                # `max-w-xs truncate` class actually bites.
                ScriptInfo(
                    src=LONG_SCRIPT_SRC,
                    has_sri=False,
                    is_first_party=False,
                    risk_level="medium",
                    category="unknown",
                ),
            ],
            total_scripts=1,
            third_party_scripts=1,
            scripts_without_sri=1,
            security_score=77,
            graded_url="http://127.0.0.1:4004/",
            critical_issues=["CSP header missing (PCI 11.6.1)"],
        ),
        integration_details=IntegrationResult(
            detected_stack={"shopify": ["HTML contains 'myshopify.com'", "Meta tag: shopify-checkout-api-token"]},
            recommended_product="Razorpay Payment Button",
            recommendation_reason="Shopify stores are served by the official app.",
            docs_url="https://razorpay.com/integrations/shopify/",
            integration_method="Shopify app",
            starter_code=(
                "# Razorpay on Shopify\n\n## Steps\n\n"
                + LONG_CODE_LINE
                + "\n"
                + "\n".join(TALL_BODY_LINES)
                + f"\n\n{LAST_CODE_LINE}\n"
            ),
            starter_code_language="markdown",
        ),
        generated_policies=PolicyGenResult(
            policies_needed=["refund_policy"],
            generated_policies=[
                GeneratedPolicy(
                    policy_type="refund_policy",
                    content="# Refund Policy\n\n" + "\n".join(TALL_BODY_LINES) + "\n",
                    tailored_to="ecommerce",
                    word_count=sum(len(line.split()) for line in TALL_BODY_LINES),
                ),
            ],
        ),
        estimated_fix_time="1-2 days to add the missing policies and fix the contact details",
        audit_trail=[
            AuditLogEntry(
                timestamp="2026-08-30T09:54:53Z",
                agent="WebCrawler",
                action="Crawled http://127.0.0.1:4004/",
                result="Found 8 pages, 6 scripts, 5 policy pages identified",
                duration_ms=5800.0,
            ),
        ],
    )


def _seed(db_path: Path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            AuditRun(
                job_id=JOB_ID,
                website_url="http://127.0.0.1:4004/",
                status="completed",
                overall_score=86,
                grade="B",
                report_json=json.dumps(_fixture_report().model_dump(mode="json")),
                completed_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    engine.dispose()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def served_report(tmp_path_factory):
    """The real app, serving the built SPA, with one report already in the database."""
    if not (DIST / "index.html").exists():
        # Skipping locally is a convenience. Skipping on CI would turn this whole file into a
        # green no-op the first time the build step broke, which is the failure mode these
        # tests exist to catch in the first place.
        message = "frontend/dist is not built; run `npm run build` in frontend/"
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)

    tmp = tmp_path_factory.mktemp("print-layout")
    db_path = tmp / "print.db"
    _seed(db_path)

    port = _free_port()
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"}
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "backend.main:app", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        import urllib.error
        import urllib.request

        for _ in range(60):
            try:
                urllib.request.urlopen(f"{base}/api/health", timeout=1).read()
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        else:
            pytest.fail("the app never came up")
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    """One Chromium for the module.

    Playwright's sync API refuses to start inside a running asyncio loop, and by the time a
    test body runs there is one. Opening the browser in a fixture keeps that out of the tests.
    """
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            yield b
        finally:
            b.close()


def _open_report(browser, base_url):
    """Sign in and land on the report, at A4's printable width."""
    page = browser.new_page(viewport={"width": A4_CONTENT_PX, "height": 1000})
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")
    page.fill('input[type="email"]', "demo@mcie.dev")
    page.fill('input[type="password"]', "demo1234")
    page.click('button[type="submit"]')
    page.wait_for_url("**/dashboard", timeout=15000)

    page.goto(f"{base_url}/dashboard/report/{JOB_ID}", wait_until="domcontentloaded")
    page.wait_for_selector("h1", timeout=15000)
    return page


@pytest.fixture(scope="module")
def print_page(browser, served_report):
    """The report page, laid out at A4's printable width with print media applied."""
    page = _open_report(browser, served_report)

    # A fixture the UI cannot render puts the error boundary on screen, which has no cards, no
    # code block and nothing that overflows, so every measurement below would pass on a page
    # that never showed the report. Fail loudly instead.
    rendered = page.inner_text("body")
    assert "Something broke in the interface" not in rendered, rendered[:400]

    # Chrome fires beforeprint and then lays the page out for paper. Doing both here is what
    # makes this the same page the print dialog sees.
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    page.emulate_media(media="print")
    page.wait_for_timeout(400)
    try:
        yield page
    finally:
        page.close()


def test_no_content_runs_off_the_right_edge_of_the_paper(print_page):
    """A code block that does not wrap is not scrolled on paper, it is cut off and lost.

    The starter code is a <pre>. On screen its wrapper scrolls sideways; the print stylesheet
    made the wrapper `overflow: visible`, which stops the clipping at the wrapper and moves it
    to the page edge instead. The fix is to wrap the text, not to reveal the overflow.
    """
    overflowing = print_page.evaluate(
        """() => [...document.querySelectorAll('body *')]
            .filter(el => el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1)
            .map(el => ({
              tag: el.tagName,
              cls: (el.className || '').toString().slice(0, 60),
              clientWidth: el.clientWidth,
              scrollWidth: el.scrollWidth,
              text: (el.textContent || '').trim().slice(0, 60),
            }))"""
    )
    assert overflowing == [], f"content is clipped at the page margin: {overflowing}"


def test_the_long_code_line_survives_the_page_width(print_page):
    """The overflow measurement above can be satisfied by hiding the text. This checks it is
    still there, and still inside the paper."""
    box = print_page.evaluate(
        """(line) => {
          const pre = [...document.querySelectorAll('pre')]
            .find(el => (el.textContent || '').includes(line));
          if (!pre) return null;
          const r = pre.getBoundingClientRect();
          return {right: r.right, docWidth: document.documentElement.clientWidth};
        }""",
        LONG_CODE_LINE,
    )
    assert box is not None, "the starter code block is not in the printed report at all"
    assert box["right"] <= box["docWidth"] + 1, (
        f"the code block reaches {box['right']}px on a {box['docWidth']}px page"
    )


def test_cards_are_not_split_down_the_middle_by_a_page_break(print_page):
    """The rule said "cards, list rows and table rows". It selected `article, section, li, tr`,
    and a Card renders a <div>, so no card was ever protected. The one element it did select,
    the tab panel, is taller than a page, which a browser answers by starting it on a fresh one
    and leaving the previous page mostly blank."""
    unprotected = print_page.evaluate(
        """() => [...document.querySelectorAll('[data-print-card]')]
            .filter(el => getComputedStyle(el).breakInside !== 'avoid').length"""
    )
    total = print_page.evaluate("() => document.querySelectorAll('[data-print-card]').length")
    assert total > 0, "no card is marked for print pagination"
    assert unprotected == 0, f"{unprotected} of {total} cards may be split across a page break"


def test_a_tab_panel_is_not_marked_unbreakable(print_page):
    """A panel is taller than a page, so `break-inside: avoid` cannot be honoured. All it does
    is push the panel to a fresh page, which is where the blank half-pages came from."""
    avoided = print_page.evaluate(
        """() => [...document.querySelectorAll('section')]
            .filter(el => getComputedStyle(el).breakInside === 'avoid')
            .map(el => (el.textContent || '').trim().slice(0, 40))"""
    )
    assert avoided == [], f"panels forced onto a fresh page: {avoided}"


def test_nothing_is_truncated_with_an_ellipsis_on_paper(print_page):
    """Paper has no hover and no tooltip, so a clamped title is text the reader cannot recover.
    The long gap title printed as "review whether..."."""
    clamped = print_page.evaluate(
        """() => [...document.querySelectorAll('body *')]
            .filter(el => {
              // getClientRects is empty for anything the print layout drops, including the
              // sidebar. Reading `display` on the element alone reports its own value even
              // when an ancestor is hidden, which listed chrome that never reaches the paper.
              if (el.getClientRects().length === 0) return false;
              if (!(el.textContent || '').trim()) return false;
              const s = getComputedStyle(el);
              return s.textOverflow === 'ellipsis' || s.webkitLineClamp !== 'none';
            })
            .map(el => (el.textContent || '').trim().slice(0, 50))"""
    )
    assert clamped == [], f"text is truncated in the printed report: {clamped}"


def test_the_full_script_url_is_on_the_paper(print_page):
    """The companion to the rule above: proving nothing computes an ellipsis is not the same as
    proving the characters survived. The inventory exists to be audited, so the source has to be
    readable in full."""
    visible = print_page.evaluate(
        """(src) => {
          const cell = [...document.querySelectorAll('td, span')]
            .find(el => (el.textContent || '').trim() === src);
          if (!cell) return null;
          return {scrollWidth: cell.scrollWidth, clientWidth: cell.clientWidth};
        }""",
        LONG_SCRIPT_SRC,
    )
    assert visible is not None, "the script inventory does not carry the full source URL"
    assert visible["scrollWidth"] <= visible["clientWidth"] + 1, (
        "the source URL is wider than its cell, so the printed report clips it"
    )


def test_nothing_is_cut_off_at_the_bottom_of_a_scrolling_box(print_page):
    """A box that scrolls on screen has nowhere to scroll to on paper.

    The starter code and every drafted policy render inside a 28rem cap. The print stylesheet
    lifted `overflow` on those, but the cap is an inline `max-height` and the wrapper around it
    is `overflow-hidden`, which the stylesheet never mentioned. So the box stayed 28rem tall and
    silently cut the rest, which is most of a policy document.
    """
    clipped = print_page.evaluate(
        """() => [...document.querySelectorAll('body *')]
            .filter(el => {
              if (el.getClientRects().length === 0) return false;
              if (el.scrollHeight <= el.clientHeight + 1) return false;
              const s = getComputedStyle(el);
              return s.overflowY !== 'visible' || s.maxHeight !== 'none';
            })
            .map(el => ({
              cls: (el.className || '').toString().slice(0, 50),
              maxHeight: getComputedStyle(el).maxHeight,
              clientHeight: el.clientHeight,
              scrollHeight: el.scrollHeight,
            }))"""
    )
    assert clipped == [], f"content is cut off below the fold on paper: {clipped}"


def test_the_end_of_the_starter_code_and_the_policy_reach_the_paper(print_page):
    """The measurement above proves no box is capped. This proves the text actually rendered,
    so the rule cannot be satisfied by dropping the content instead of showing it."""
    text = print_page.inner_text("body")
    assert LAST_CODE_LINE in text, "the printed report stops before the end of the starter code"
    assert LAST_POLICY_LINE in text, "the printed report stops before the end of the policy"


def test_the_printed_report_shows_the_score(print_page):
    text = print_page.inner_text("body")
    assert "86" in text, f"the printed report does not show the score 86: {text[:120]!r}"


def test_printing_mid_animation_still_prints_the_real_score(browser, served_report):
    """The ring counts up from zero over 900ms, so a report printed during that second shows a
    number the engine never produced, permanently, in a file the merchant keeps.

    The browser fires `beforeprint` before it lays the page out for paper, which is the moment
    to abandon the animation. This opens its own page so the read happens while the count-up is
    still running; on a machine slow enough for 900ms to pass first the assertion is simply
    true for the other reason, so it cannot flake, only under-report.
    """
    page = _open_report(browser, served_report)
    try:
        page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
        page.wait_for_timeout(60)  # one React flush, far inside the 900ms count-up
        shown = page.evaluate(
            """() => {
              const el = [...document.querySelectorAll('span, div')]
                .find(e => /^\\d{1,3}$/.test((e.textContent || '').trim()));
              return el ? el.textContent.trim() : null;
            }"""
        )
        assert shown == "86", f"the ring printed {shown} for a report that scored 86"
    finally:
        page.close()


def test_the_printed_report_identifies_the_merchant_and_the_scan(print_page):
    """A PDF leaves the app. On its own it has to say which site was scanned, which run it was,
    and when, or it is an anonymous page of findings."""
    text = print_page.inner_text("body")
    assert "127.0.0.1:4004" in text, "the printed report does not name the site it scanned"
    assert JOB_ID in text, "the printed report does not carry the scan id"


def test_export_pdf_does_not_set_a_class_no_stylesheet_reads():
    """`document.body.classList.add('printing')` was doing nothing: no rule anywhere selects
    `.printing`. Declared in one place and not honoured by the code that runs is this project's
    house bug, and it was sitting in the PDF path itself."""
    source = (REPO_ROOT / "frontend" / "src" / "features" / "report" / "exportReport.ts").read_text()
    css = (REPO_ROOT / "frontend" / "src" / "index.css").read_text()
    for token in ("'printing'", '"printing"'):
        if token in source:
            assert ".printing" in css, (
                "exportReport adds a `printing` class that no stylesheet reads"
            )
