"""Serve the four synthetic test sites with the security headers they declare.

`npx serve` ignores `vercel.json`, so served locally every site reported every security header as
missing. PCI-004 and PCI-005 could not tell the four sites apart, Artisan's planted fault (four
headers set, no CSP) was indistinguishable from FreshKart's (nothing set at all), and 25 of the
100 PCI points were decided by the serving method rather than by the site.

Run all four:      uv run python test-sites/serve.py
Run one:           uv run python test-sites/serve.py artisan-weaves
"""
from __future__ import annotations

import json
import re
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

# The ports the READMEs, the demo buttons and the ground-truth fixtures all assume.
SITES: dict[str, int] = {
    "freshkart-india": 4001,
    "quickbites-delivery": 4002,
    "clouddesk-saas": 4003,
    "artisan-weaves": 4004,
}


def declared_headers(site_dir: Path) -> dict[str, str]:
    """The headers a site's `vercel.json` promises for every path.

    A rule with an empty header list is a planted fault and returns nothing, which is different
    from a file that cannot be parsed. A `source` this cannot apply raises rather than being
    skipped, for the same reason the PCI scorer raises on a deduction it cannot parse.
    """
    config = site_dir / "vercel.json"
    if not config.exists():
        return {}

    headers: dict[str, str] = {}
    for rule in json.loads(config.read_text(encoding="utf-8")).get("headers", []):
        source = rule.get("source", "")
        if not re.fullmatch(r"/\(\.\*\)|/\*\*?", source):
            raise ValueError(
                f"{config} declares source {source!r}, which this server cannot apply. "
                "Serving a site whose declared headers are silently dropped is what this "
                "script exists to prevent."
            )
        for header in rule.get("headers", []):
            headers[header["key"]] = header["value"]
    return headers


def _handler_for(site_dir: Path):
    site_headers = declared_headers(site_dir)

    class Handler(SimpleHTTPRequestHandler):
        # Default is "SimpleHTTP/0.6 Python/3.12". A static host does not announce Python, and
        # the stack detector reads response headers, so leaving it in feeds a signal the real
        # deployment would never send.
        server_version = "static"
        sys_version = ""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)

        def end_headers(self):
            for key, value in site_headers.items():
                self.send_header(key, value)
            super().end_headers()

        def log_message(self, *args):
            pass  # the crawler generates a lot of these and none of them are interesting

    return Handler


def serve(site: str, port: int) -> ThreadingHTTPServer:
    site_dir = _ROOT / site
    if not site_dir.is_dir():
        raise SystemExit(f"no such test site: {site_dir}")

    server = ThreadingHTTPServer(("127.0.0.1", port), _handler_for(site_dir))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    sent = declared_headers(site_dir)
    summary = ", ".join(sorted(sent)) if sent else "no security headers declared"
    print(f"  {site:<22} http://127.0.0.1:{port}   {summary}")
    return server


def main(argv: list[str]) -> int:
    wanted = argv[1:] or list(SITES)
    unknown = [s for s in wanted if s not in SITES]
    if unknown:
        raise SystemExit(f"unknown site(s): {', '.join(unknown)}. Known: {', '.join(SITES)}")

    print("Serving test sites with their declared headers:")
    servers = [serve(site, SITES[site]) for site in wanted]
    print("\nCtrl-C to stop.")

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        for server in servers:
            server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
