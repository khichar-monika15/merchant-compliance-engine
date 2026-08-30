"""The UI states facts about the engine. These check the countable ones against the engine.

The landing page advertises agent and check counts, the scan form offers business types, and the
demo buttons carry the KYC names that reproduce the published scores. Every one of those is a
hardcoded copy of something the backend owns, and nothing kept them honest: the page could claim
any number and the build stayed green.

Only mechanically checkable claims live here. Prose claims are reviewed by reading.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend import knowledge as kb

_FRONTEND = Path("frontend/src")
_GT_DIR = Path("backend/tests/ground_truth")
_AGENTS_DIR = Path("backend/agents")


def _read(relative: str) -> str:
    return (_FRONTEND / relative).read_text(encoding="utf-8")


def _agent_modules() -> list[str]:
    """The specialist agents, excluding the graph itself and the shared audit helper."""
    return sorted(
        p.stem
        for p in _AGENTS_DIR.glob("*.py")
        if p.stem not in {"__init__", "_audit", "orchestrator"}
    )


class TestLandingPageMetrics:
    """`LandingPage.METRICS` carries a comment saying every number is measured."""

    @pytest.fixture(scope="class")
    def metrics(self) -> dict[str, tuple[str, str]]:
        source = _read("pages/LandingPage.tsx")
        block = re.search(r"const METRICS = \[(.*?)\n\]", source, re.S)
        assert block, "could not find the METRICS array in LandingPage.tsx"
        entries = re.findall(
            r"\{\s*value:\s*'([^']*)',\s*label:\s*'([^']*)',\s*detail:\s*'([^']*)'",
            block.group(1),
        )
        assert entries, "METRICS parsed as empty, the shape of the array changed"
        return {label: (value, detail) for value, label, detail in entries}

    def test_agent_count_matches_the_orchestrator(self, metrics):
        value, _ = metrics["specialist agents"]
        assert int(value) == len(_agent_modules()), (
            f"the landing page claims {value} agents; backend/agents holds "
            f"{len(_agent_modules())}: {_agent_modules()}"
        )

    def test_check_count_matches_the_knowledge_base(self, metrics):
        value, detail = metrics["compliance checks"]
        rbi, pci = len(kb.rbi_checks()), len(kb.pci_checks())
        assert int(value) == rbi + pci, (
            f"the landing page claims {value} checks; the knowledge base declares {rbi + pci}"
        )
        assert f"{rbi} RBI" in detail and f"{pci} PCI" in detail, (
            f"the breakdown '{detail}' does not match {rbi} RBI and {pci} PCI checks"
        )


class TestBusinessTypesAreReal:
    """Every option in the scan form claims to change which policy checklist variant applies."""

    def test_every_offered_type_has_a_variant(self):
        source = _read("features/scan/MerchantScanForm.tsx")
        block = re.search(r"const BUSINESS_TYPES = \[(.*?)\n\]", source, re.S)
        assert block, "could not find BUSINESS_TYPES"
        offered = {v for v in re.findall(r"value:\s*'([^']*)'", block.group(1)) if v}

        declared: set[str] = set()
        for check in kb.rbi_checks():
            declared |= set(check.get("business_type_variations", {}))

        inert = sorted(offered - declared)
        assert not inert, (
            f"the scan form offers {inert} and tells the user it changes the checklist variant, "
            f"but the knowledge base only declares variants for {sorted(declared)}. Either add "
            f"the variant or stop offering the option."
        )


class TestDemoSitesMatchGroundTruth:
    """The demo buttons prefill the KYC names that reproduce the published score."""

    @pytest.fixture(scope="class")
    def demo_sites(self) -> dict[str, dict]:
        source = _read("scan/demoSites.ts")
        blocks = re.findall(
            r"\{\s*key:\s*'([^']*)',\s*label:\s*'[^']*',\s*expected:\s*'([^']*)',\s*"
            r"grade:\s*'([^']*)',\s*merchant:\s*\{(.*?)\n    \},",
            source,
            re.S,
        )
        assert len(blocks) == 4, f"expected 4 demo sites, parsed {len(blocks)}"
        parsed = {}
        for key, expected, grade, merchant in blocks:
            fields = dict(re.findall(r"(\w+):\s*'([^']*)'", merchant))
            parsed[key] = {"expected": expected, "grade": grade, **fields}
        return parsed

    @pytest.fixture(scope="class")
    def fixtures(self) -> dict[str, dict]:
        return {
            path.stem.replace("_expected", ""): json.loads(path.read_text())
            for path in _GT_DIR.glob("*_expected.json")
        }

    def test_every_demo_site_has_a_fixture(self, demo_sites, fixtures):
        assert set(demo_sites) == set(fixtures), (
            f"demo buttons {sorted(demo_sites)} do not line up with ground truth "
            f"{sorted(fixtures)}"
        )

    def test_kyc_names_and_url_match(self, demo_sites, fixtures):
        for key, site in demo_sites.items():
            gt = fixtures[key]
            assert site["website_url"] == gt["served_on"], key
            assert site["pan_name"] == gt["kyc_input"]["pan_name"], key
            assert site["gst_legal_name"] == gt["kyc_input"]["gst_name"], key
            assert site["bank_account_name"] == gt["kyc_input"]["bank_name"], key

    def test_advertised_score_and_grade_match(self, demo_sites, fixtures):
        """The button must advertise the score the engine produces, not merely a plausible one.

        This asserted only that the advertised number fell inside `expected_score_range`, a band
        up to 15 points wide. QuickBites went on advertising 28 after RBI-007 moved it to 26, and
        the guard stayed green because 28 is inside 25 to 40.
        """
        for key, site in demo_sites.items():
            gt = fixtures[key]
            assert int(site["expected"]) == gt["measured_score_rule_path"], (
                f"{key}: the button advertises {site['expected']}, the engine produces "
                f"{gt['measured_score_rule_path']} on the rule path"
            )
            assert site["grade"] == gt["expected_grade"], key

    def test_the_exact_score_is_inside_the_harness_band(self, fixtures):
        """The band exists to tolerate the LLM path; it still has to contain the rule-path value."""
        for key, gt in fixtures.items():
            low, high = gt["expected_score_range"]
            exact = gt["measured_score_rule_path"]
            assert low <= exact <= high, f"{key}: measured {exact} is outside its own band {low}-{high}"


class TestChecksPageDoesNotRestateTheScoring:
    """The page's own thesis is that it cannot drift, so it must not hardcode a threshold."""

    def test_grade_bands_are_not_hardcoded(self):
        source = _read("pages/ChecksPage.tsx")
        thresholds = {str(t) for t, _ in _grade_thresholds() if t}
        # Deliberately not skipping lines that mention min_score: the line that hardcoded the
        # F band read `g.min_score === 0 ? 'below 25' : ...`, so skipping them skipped the bug.
        offenders = [
            line.strip()
            for line in source.splitlines()
            if not line.strip().startswith("//")
            and any(str(t) in line for t in thresholds)
        ]
        assert not offenders, (
            f"ChecksPage restates a grade threshold instead of rendering the payload it "
            f"already receives: {offenders}"
        )


def _grade_thresholds():
    from backend.agents.report_generator import _GRADE_THRESHOLDS

    return _GRADE_THRESHOLDS


class TestReadmeTestCount:
    """The README quotes a test count. It said 177 while the suite was 363.

    A number a human retypes goes stale silently, which is the same failure as a rule nobody
    applies. This one is checked against the collector.
    """

    def test_readme_count_matches_the_collector(self):
        import re
        import subprocess

        readme = Path("README.md").read_text(encoding="utf-8")
        stated = re.search(r"#\s*(\d+)\s*tests", readme)
        assert stated, "README no longer states a test count in the quickstart block"

        out = subprocess.run(
            ["python", "-m", "pytest", "backend/tests/", "--collect-only", "-q"],
            capture_output=True, text=True, check=False,
        ).stdout
        collected = re.search(r"(\d+) tests collected", out)
        assert collected, f"could not read a collected count from pytest:\n{out[-400:]}"

        assert int(stated.group(1)) == int(collected.group(1)), (
            f"README says {stated.group(1)} tests, the suite collects {collected.group(1)}"
        )


class TestNoDeadFrontendExports:
    """An exported symbol nothing references is a declaration the app does not honour.

    `isTracking` sat exported in scanSocket.ts, called by nothing, not even its own module.
    TypeScript's noUnusedLocals catches unused locals and imports; it says nothing about an
    export, because an export is assumed to be someone else's entry point. Here there is no
    someone else: this is a leaf application, not a library.
    """

    DECLARATION = re.compile(
        r"^export\s+(?:default\s+)?(?:async\s+)?"
        r"(?:function|const|class|interface|type|enum)\s+(\w+)",
        re.M,
    )

    @staticmethod
    def _sources() -> dict[Path, str]:
        return {p: p.read_text(encoding="utf-8") for p in _FRONTEND.rglob("*.ts*")}

    def test_every_export_is_referenced(self):
        sources = self._sources()
        dead = []

        for path, text in sources.items():
            for match in self.DECLARATION.finditer(text):
                name = match.group(1)
                pattern = re.compile(rf"\b{re.escape(name)}\b")
                # Count references everywhere except the line that declares the symbol. The
                # declaring file counts: a type used only as an annotation beside its own
                # definition is legitimately used, and treating that as dead was wrong.
                declaring_line = text[: match.start()].count("\n")
                refs = 0
                for other, body in sources.items():
                    for i, line in enumerate(body.splitlines()):
                        if other == path and i == declaring_line:
                            continue
                        if pattern.search(line):
                            refs += 1
                if refs == 0:
                    dead.append(f"{name} ({path})")

        assert not dead, (
            "exported and referenced nowhere, so nothing honours the declaration: "
            f"{sorted(dead)}"
        )


class TestThePrintedReportKeepsItsContent:
    """The PDF export is the print stylesheet, so a CSS rule can silently delete report content.

    `button { display: none }` in the print block removed the entire gap list from the PDF,
    because each finding is an accordion whose row is a <button>. The most important part of the
    report printed as an empty panel and nothing failed.
    """

    @staticmethod
    def _print_block() -> str:
        css = _read("index.css")
        start = css.index("@media print")
        depth, i = 0, start
        while i < len(css):
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
                if depth == 0:
                    return css[start:i + 1]
            i += 1
        raise AssertionError("@media print block is not balanced")

    @staticmethod
    def _hidden_selectors(block: str) -> set[str]:
        """Every selector the print block sets to `display: none`.

        Parsed from the rule bodies rather than by scanning lines: the first version of this test
        matched a line equal to "button" and the real stylesheet writes "button {", so restoring
        the bug left it green. Written by watching it fail.
        """
        hidden: set[str] = set()
        # Comments first: they contain commas, and splitting a selector list on commas before
        # removing them left "/*" and "*/" in different pieces, so nothing parsed cleanly.
        block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        body = block[block.index("{") + 1:block.rindex("}")]
        for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
            if "display" in declarations and "none" in declarations:
                for part in selector.split(","):
                    cleaned = part.strip()
                    if cleaned:
                        hidden.add(cleaned)
        return hidden

    def test_print_does_not_blanket_hide_buttons(self):
        hidden = self._hidden_selectors(self._print_block())
        assert "button" not in hidden, (
            "the print stylesheet hides every button. Each finding in the gap list is an "
            f"accordion whose row is a <button>, so this empties the PDF. Hidden: {sorted(hidden)}"
        )

    def test_the_guard_can_see_what_the_stylesheet_hides(self):
        """A parser that finds nothing would make the test above pass for the wrong reason."""
        hidden = self._hidden_selectors(self._print_block())
        assert "[data-print-hide]" in hidden, (
            f"the selector parser did not find the rules it is meant to read: {sorted(hidden)}"
        )

    def test_print_undoes_the_dashboard_shell(self):
        """A fixed sidebar and a 240px content inset print as an empty column."""
        block = self._print_block()
        for needed in ("[data-print-main]", ".fixed", ".sticky"):
            assert needed in block, f"print stylesheet never neutralises {needed}"

    def test_the_gap_detail_is_not_conditionally_mounted(self):
        """CSS cannot reveal what React never rendered."""
        source = _read("features/report/tabs/OverviewTab.tsx")
        assert "print:block" in source, (
            "the gap detail is not marked to appear in print, so the PDF gets bare titles"
        )
        assert "{open && (" not in source, (
            "the gap detail is only mounted when expanded, so it cannot reach the PDF"
        )

    def test_every_report_tab_reaches_the_pdf(self):
        """Only the open tab used to be mounted, so a PDF held one seventh of the report."""
        source = _read("pages/ReportPage.tsx")
        assert "print:block" in source, "inactive report tabs are not revealed for print"
        assert "active === 'compliance' &&" not in source, (
            "tabs are still mounted only when active, so the PDF holds one tab"
        )


class TestTheAssistantCarriesItsDisclaimer:
    """The assistant may answer beyond the knowledge base, so the disclaimer is the mitigation.

    It is the thing that makes the wider scope defensible rather than a liability, so it is not
    optional decoration and a refactor must not quietly drop it.
    """

    def test_the_panel_says_answers_can_be_wrong(self):
        """Pinned to the meaning, not the sentence, so rewording it does not break the build."""
        source = _read("features/assistant/AssistantWidget.tsx")
        assert "AI-generated" in source, (
            "the assistant panel no longer warns that answers are AI-generated"
        )
        assert re.search(r"can be wrong|may be wrong|check anything", source), (
            "the disclaimer no longer warns the answer can be wrong"
        )

    def test_the_panel_explains_what_a_citation_means(self):
        """A check badge is the reader's only signal that a claim is grounded in a real rule."""
        source = _read("features/assistant/AssistantWidget.tsx")
        assert re.search(r"[Tt]agged answers|check id", source), (
            "the disclaimer does not explain the citation badges"
        )

    def test_citations_are_rendered(self):
        source = _read("features/assistant/AssistantWidget.tsx")
        assert "cited" in source and "Badge" in source, (
            "the panel does not render the cited check ids the backend returns"
        )


class TestDashboardCheckCounts:
    """The dashboard restates how many checks exist, and that sentence went stale.

    It read "Eleven checks ... six from the RBI Merchant Due Diligence checklist" for as long as
    RBI-007 had existed. The landing page's counts were guarded; this sentence was not, which is
    the only reason it drifted.
    """

    def test_the_counts_match_the_knowledge_base(self):
        source = _read("pages/DashboardHome.tsx")
        rbi, pci = len(kb.rbi_checks()), len(kb.pci_checks())

        match = re.search(
            r"(\d+) checks with formal identifiers:\s*(\d+) from the RBI[\s\S]{0,80}?(\d+) from PCI",
            source,
        )
        assert match, "the dashboard no longer states check counts in the expected shape"

        total, stated_rbi, stated_pci = (int(g) for g in match.groups())
        assert (total, stated_rbi, stated_pci) == (rbi + pci, rbi, pci), (
            f"the dashboard says {total} checks ({stated_rbi} RBI, {stated_pci} PCI); the "
            f"knowledge base declares {rbi + pci} ({rbi} RBI, {pci} PCI)"
        )


class TestTheChecksPageCanGetBack:
    """Opened from the dashboard, the only way back used to be out of the app entirely."""

    def test_the_back_link_is_not_hardcoded_home(self):
        source = _read("pages/ChecksPage.tsx")
        assert "backTo" in source, "the checks page back link is not derived from where you came from"

    def test_the_dashboard_says_where_it_linked_from(self):
        source = _read("pages/DashboardHome.tsx")
        assert "from: '/dashboard'" in source, (
            "the dashboard links to /checks without saying where the reader came from, so the "
            "checks page cannot send them back"
        )


class TestAssistantSuggestionsMatchTheContext:
    """A prompt has to make sense where it is shown.

    The panel offered "Why did I get this score?" on a dashboard with no scans. The answer was
    correct, it explained there was no score, but a suggestion the app knows cannot apply reads
    as a broken assistant.
    """

    def test_there_are_two_suggestion_sets(self):
        source = _read("features/assistant/AssistantWidget.tsx")
        assert "REPORT_SUGGESTIONS" in source and "GENERAL_SUGGESTIONS" in source, (
            "the assistant offers one set of suggestions regardless of whether a report is open"
        )

    def test_score_questions_are_only_offered_with_a_report(self):
        source = _read("features/assistant/AssistantWidget.tsx")
        general = re.search(r"const GENERAL_SUGGESTIONS = \[(.*?)\n\]", source, re.S)
        assert general, "could not parse GENERAL_SUGGESTIONS"

        offered = re.findall(r"'([^']+)'", general.group(1))
        assert offered, "GENERAL_SUGGESTIONS is empty"
        for question in offered:
            assert not re.search(r"\bmy\b|\bthis score\b|\bI get\b|\bfix first\b", question), (
                f"{question!r} assumes a report is open, but it is offered when none is"
            )

    def test_the_chosen_set_depends_on_the_job(self):
        source = _read("features/assistant/AssistantWidget.tsx")
        assert re.search(r"jobId \? REPORT_SUGGESTIONS : GENERAL_SUGGESTIONS", source), (
            "suggestions are not selected by whether a report is open"
        )


class TestTheAssistantGlowIsDrivenByState:
    """A CSS :hover rule here was correct and unverifiable, and shipped broken twice.

    React state can be driven by a dispatched event in a test or a browser check, so the glow is
    something that can actually be proven to work rather than eyeballed.
    """

    def test_hover_is_tracked_in_state(self):
        source = _read("features/assistant/AssistantWidget.tsx")
        assert "onMouseEnter" in source and "onMouseLeave" in source, (
            "the glow depends on a CSS :hover rule, which cannot be verified programmatically"
        )
        assert "hovered && 'animate-pulse-glow'" in source

    def test_keyboard_focus_glows_too(self):
        source = _read("features/assistant/AssistantWidget.tsx")
        assert "onFocus" in source and "onBlur" in source, (
            "the glow is mouse-only, so a keyboard user never sees the affordance"
        )

    def test_the_keyframes_exist(self):
        config = Path("frontend/tailwind.config.js").read_text(encoding="utf-8")
        assert "pulseGlow" in config and "pulse-glow" in config, (
            "the animation the widget asks for is not defined"
        )
