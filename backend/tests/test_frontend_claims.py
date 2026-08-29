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
        for key, site in demo_sites.items():
            gt = fixtures[key]
            low, high = gt["expected_score_range"]
            assert low <= int(site["expected"]) <= high, (
                f"{key}: the button advertises {site['expected']}, outside the ground truth "
                f"range {low} to {high}"
            )
            assert site["grade"] == gt["expected_grade"], key


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
