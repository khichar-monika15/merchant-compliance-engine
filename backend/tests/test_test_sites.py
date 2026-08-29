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
        dirs = {
            p.name for p in _SITES.iterdir()
            if p.is_dir() and not p.name.startswith((".", "__"))
        }
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

    def test_the_readme_documents_the_header_applying_server(self):
        """The ports now live in serve.py, checked against the fixtures elsewhere in this file.

        What the README must not do is send a reader to `npx serve`, which drops every declared
        header and makes the scores in its own table unreproducible.
        """
        readme = (_SITES / "README.md").read_text(encoding="utf-8")
        assert "test-sites/serve.py" in readme, "the README does not document the serve command"

        instructions = readme.split("## Serve locally", 1)[1].split("##", 1)[0]
        assert not re.search(r"^\s*npx serve", instructions, re.M), (
            "the README still instructs a reader to serve with npx serve"
        )

    @pytest.mark.parametrize("key", CASES)
    def test_score_matches_the_measured_value_exactly(self, key):
        """The table is a published number, so it is pinned to the measurement, not to a band.

        This checked the range, which is up to 15 points wide to tolerate the LLM path. QuickBites
        sat at 28 in this table after the engine started producing 26 and nothing noticed.
        """
        gt = FIXTURES[key]
        row = _readme_table()[gt["site"]]
        assert row["score"] == gt["measured_score_rule_path"], (
            f"README quotes {row['score']} for {gt['site']}, the engine produces "
            f"{gt['measured_score_rule_path']} on the rule path"
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


def _serve_module():
    """`test-sites` has a hyphen, so it is loaded by path rather than imported."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("test_sites_serve", _SITES / "serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheServerSendsWhatEachSiteDeclares:
    """A declared header that never reaches the wire is an inert rule like any other.

    `npx serve` ignores vercel.json, so all four sites reported every header missing and PCI-004
    and PCI-005 could not separate a site with four correct headers from one with none. That made
    25 of the 100 PCI points a property of the serving method rather than of the site.
    """

    @pytest.mark.parametrize("key", CASES)
    def test_declared_headers_arrive_over_http(self, key):
        import urllib.request

        serve = _serve_module()
        site = FIXTURES[key]["site"]
        declared = serve.declared_headers(_SITES / site)

        server = serve.serve(site, 0)
        try:
            port = server.server_address[1]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
                received = {k.lower(): v for k, v in response.headers.items()}

            for name, value in declared.items():
                assert received.get(name.lower()) == value, (
                    f"{site} declares {name}: {value} and the server sent "
                    f"{received.get(name.lower())!r}"
                )
        finally:
            server.shutdown()
            server.server_close()

    def test_the_four_sites_are_not_all_identical(self):
        """The whole point: the header suite has to discriminate between these sites."""
        serve = _serve_module()
        counts = {
            site: len(serve.declared_headers(_SITES / site))
            for site in (FIXTURES[k]["site"] for k in CASES)
        }
        assert len(set(counts.values())) > 1, (
            f"every site declares the same number of headers, so PCI-005 cannot tell them "
            f"apart: {counts}"
        )

    def test_every_port_is_declared_once(self):
        serve = _serve_module()
        assert len(set(serve.SITES.values())) == len(serve.SITES)
        for key in CASES:
            site = FIXTURES[key]["site"]
            expected = int(FIXTURES[key]["served_on"].rsplit(":", 1)[1])
            assert serve.SITES[site] == expected, (
                f"{site} is served on {serve.SITES[site]} but its fixture expects {expected}"
            )
