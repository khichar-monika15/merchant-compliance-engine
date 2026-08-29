"""The test sites and their fixtures describe each other. Neither side checked the other.

`site` sat in every ground-truth fixture naming a directory, read by nothing, so renaming a
directory would have left the fixture pointing at a name that no longer existed. The ports and
scores in `test-sites/README.md` were retyped by hand, and the SRI count in that table went
stale in three places at once when the PCI-002 exemption changed it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_SITES = Path("test-sites")
_GT_DIR = Path("backend/tests/ground_truth")
_HREF = re.compile(r'href=["\']([^"\'#?]+)', re.I)


def _fixtures() -> dict[str, dict]:
    return {p.stem.replace("_expected", ""): json.loads(p.read_text()) for p in _GT_DIR.glob("*.json")}


def _readme_table() -> dict[str, dict]:
    """Parse the site table out of test-sites/README.md, keyed by directory name."""
    rows = {}
    for line in (_SITES / "README.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*`([\w-]+)/`\s*\|\s*(\d+)\s*\|[^|]*\|\s*(\d+)\s*\|\s*([A-F])\s*\|", line)
        if match:
            name, port, score, grade = match.groups()
            rows[name] = {"port": int(port), "score": int(score), "grade": grade}
    return rows


FIXTURES = _fixtures()
CASES = sorted(FIXTURES)


class TestFixturesAndDirectoriesAgree:
    @pytest.mark.parametrize("key", CASES)
    def test_site_names_a_real_directory(self, key):
        site = FIXTURES[key]["site"]
        assert (_SITES / site).is_dir(), (
            f"{key}_expected.json declares site '{site}', which is not a directory under "
            f"test-sites/. Nothing read this field, so it could name anything."
        )

    def test_every_site_has_a_fixture(self):
        dirs = {p.name for p in _SITES.iterdir() if p.is_dir()}
        declared = {gt["site"] for gt in FIXTURES.values()}
        assert dirs == declared, (
            f"directories without a fixture: {sorted(dirs - declared)}; "
            f"fixtures without a directory: {sorted(declared - dirs)}"
        )


class TestReadmeTableMatchesGroundTruth:
    """The table is what a reviewer reads before running anything."""

    @pytest.mark.parametrize("key", CASES)
    def test_port_matches(self, key):
        gt = FIXTURES[key]
        row = _readme_table()[gt["site"]]
        port = int(gt["served_on"].rsplit(":", 1)[1])
        assert row["port"] == port, (
            f"README lists port {row['port']} for {gt['site']}, the fixture scans {port}"
        )

    @pytest.mark.parametrize("key", CASES)
    def test_serve_command_uses_the_same_port(self, key):
        gt = FIXTURES[key]
        port = int(gt["served_on"].rsplit(":", 1)[1])
        readme = (_SITES / "README.md").read_text(encoding="utf-8")
        assert re.search(rf"npx serve test-sites/{re.escape(gt['site'])}\s+-p {port}\b", readme), (
            f"the serve command for {gt['site']} does not use port {port}"
        )

    @pytest.mark.parametrize("key", CASES)
    def test_score_and_grade_are_inside_the_expected_range(self, key):
        gt = FIXTURES[key]
        row = _readme_table()[gt["site"]]
        low, high = gt["expected_score_range"]
        assert low <= row["score"] <= high, (
            f"README quotes {row['score']} for {gt['site']}, outside the fixture range "
            f"{low} to {high}"
        )
        assert row["grade"] == gt["expected_grade"], (
            f"README grades {gt['site']} {row['grade']}, the fixture expects {gt['expected_grade']}"
        )

    @pytest.mark.parametrize("key", CASES)
    def test_quoted_sri_count_matches_the_fixture(self, key):
        """This number went stale in three documents when the SRI exemption changed it."""
        gt = FIXTURES[key]
        expected = gt.get("pci_expected", {}).get("scripts_without_sri_max")
        if expected is None:
            pytest.skip("fixture pins no SRI count")

        row_text = next(
            line for line in (_SITES / "README.md").read_text(encoding="utf-8").splitlines()
            if f"`{gt['site']}/`" in line
        )
        quoted = re.search(r"(\d+)\s+without SRI", row_text)
        if not quoted:
            pytest.skip("the table row does not quote an SRI count")
        assert int(quoted.group(1)) == expected, (
            f"README says {quoted.group(1)} without SRI for {gt['site']}, the fixture pins "
            f"{expected}"
        )


class TestSiteLinksResolve:
    """A nav link to a page that does not exist is a policy the site claims and does not have."""

    @pytest.mark.parametrize("key", CASES)
    def test_no_links_to_missing_pages(self, key):
        site = _SITES / FIXTURES[key]["site"]
        pages = {p.name for p in site.glob("*.html")}
        broken = set()
        for page in site.glob("*.html"):
            for href in _HREF.findall(page.read_text(encoding="utf-8", errors="ignore")):
                if href.startswith(("http://", "https://", "mailto:", "tel:", "//")):
                    continue
                target = href.lstrip("./").split("/")[-1] or "index.html"
                if target.endswith(".html") and target not in pages:
                    broken.add(target)
        assert not broken, f"{site.name} links to pages that do not exist: {sorted(broken)}"

    @pytest.mark.parametrize("key", CASES)
    def test_no_page_is_unreachable(self, key):
        """A planted policy nothing links to is one the crawler can never find."""
        site = _SITES / FIXTURES[key]["site"]
        pages = {p.name for p in site.glob("*.html")}
        linked = set()
        for page in site.glob("*.html"):
            for href in _HREF.findall(page.read_text(encoding="utf-8", errors="ignore")):
                if href.startswith(("http://", "https://", "mailto:", "tel:", "//")):
                    continue
                linked.add(href.lstrip("./").split("/")[-1] or "index.html")

        orphans = sorted(p for p in pages if p != "index.html" and p not in linked)
        assert not orphans, f"{site.name} has pages nothing links to: {orphans}"

    @pytest.mark.parametrize("key", CASES)
    def test_vercel_config_parses(self, key):
        config = _SITES / FIXTURES[key]["site"] / "vercel.json"
        if not config.exists():
            pytest.skip("no vercel.json")
        json.loads(config.read_text())
