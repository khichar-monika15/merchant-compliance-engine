"""Every key in every knowledge file must be honoured, and the guard must be able to say how.

The predecessor of this file scanned only `rbi_mdd_checklist.json`, only the `search` and
`quality_criteria` blocks, and concatenated all backend source including `backend/knowledge.py`
itself, so the loader's own `.get("url_patterns", ...)` satisfied the scan for four fields. Every
consumer could have reverted to a private hardcoded copy and it would still have passed. It also
missed the collision where `reason`, `category`, `headers` and `name` appear in several files, so
one file's key counted as read because another file's identically named key was.

This version walks all four files, classifies every key through `knowledge.KNOWLEDGE_FIELDS`, and
checks the access happens in the module the registry names.

**What this guard cannot do.** It matches on key name within a module, so two checks in the same
file declaring the same key name are indistinguishable to it: PCI-001 and PCI-005 both declare
`requirement`, and PCI-001's read satisfied PCI-005's while PCI-005's four requirements were
enforced by nothing. Only cross-file collisions are handled. Where a declared value has to change
behaviour, the guard that proves it is behavioural and lives next to the code, for example
`TestEveryDeclaredHeaderCostsItsDeclaredPoints` in `test_pci.py`. Do not read a pass here as proof
that a rule is applied, only that something in the named module reads a key by that name.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from backend import knowledge as kb

_KNOWLEDGE_DIR = Path("backend/knowledge")
_BACKEND = Path("backend")
_LOADER = _BACKEND / "knowledge.py"


def _source_of(module: str) -> str:
    """`backend.agents.pci_scanner` -> the text of that file."""
    return Path(module.replace(".", "/") + ".py").read_text(encoding="utf-8")


def _reads_key(source: str, key: str) -> bool:
    """A real subscript or .get() for `key`, not a passing mention in a comment or docstring."""
    return any(
        token in source
        for token in (f'get("{key}"', f"get('{key}'", f'["{key}"]', f"['{key}']")
    )


def _declared_keys(filename: str) -> dict[str, str]:
    """Every distinct key in the file, mapped to the parent key it hangs under."""
    doc = json.loads((_KNOWLEDGE_DIR / filename).read_text(encoding="utf-8"))
    found: dict[str, str] = {}

    def walk(node, parent: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                found.setdefault(key, parent)
                walk(value, key)
        elif isinstance(node, list):
            for item in node:
                walk(item, parent)

    walk(doc, "$root")
    return found


ALL_FILES = sorted(kb.KNOWLEDGE_FIELDS)


@pytest.mark.parametrize("filename", ALL_FILES)
class TestEveryKeyIsClassified:
    def test_no_unclassified_key(self, filename):
        declared = set(_declared_keys(filename))
        classified = set(kb.KNOWLEDGE_FIELDS[filename])
        missing = sorted(declared - classified)
        assert not missing, (
            f"{filename} declares keys the registry does not classify: {missing}. "
            "Say who applies each one, or mark it display, or delete it. A key nobody "
            "classified is how half of this knowledge base became inert."
        )

    def test_no_stale_registry_entry(self, filename):
        declared = set(_declared_keys(filename))
        classified = set(kb.KNOWLEDGE_FIELDS[filename])
        stale = sorted(classified - declared)
        assert not stale, (
            f"the registry classifies keys {filename} no longer declares: {stale}"
        )


class TestAppliedRulesAreActuallyApplied:
    """`applied(module)` means that module reads the key. Not 'somewhere in the backend'."""

    CASES = [
        (filename, key, rule[1])
        for filename, fields in kb.KNOWLEDGE_FIELDS.items()
        for key, rule in fields.items()
        if rule[0] == "applied"
    ]

    @pytest.mark.parametrize("filename,key,module", CASES)
    def test_named_module_reads_the_key(self, filename, key, module):
        assert _reads_key(_source_of(module), key), (
            f"{filename} declares '{key}' and the registry says {module} applies it, but that "
            f"module never reads it. Either apply the rule, or stop publishing it."
        )


class TestDisplayKeysReachThePage:
    """`display()` is not an excuse. The key must actually be served to the checks page."""

    CASES = [
        (filename, key)
        for filename, fields in kb.KNOWLEDGE_FIELDS.items()
        for key, rule in fields.items()
        if rule[0] == "display"
    ]

    @pytest.fixture(scope="class")
    def payload(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app

        with TestClient(create_app()) as client:
            return client.get("/api/knowledge").json()

    @pytest.mark.parametrize("filename,key", CASES)
    def test_key_is_served(self, filename, key, payload):
        assert key in json.dumps(payload), (
            f"{filename} declares '{key}' as display metadata, but GET /api/knowledge never "
            f"serves it, so it is displayed nowhere. Serve it or delete it."
        )


class TestDynamicKeysHangOffAnAppliedParent:
    CASES = [
        (filename, key, rule[1])
        for filename, fields in kb.KNOWLEDGE_FIELDS.items()
        for key, rule in fields.items()
        if rule[0] == "dynamic"
    ]

    @pytest.mark.parametrize("filename,key,parent", CASES)
    def test_parent_is_applied(self, filename, key, parent):
        parent_rule = kb.KNOWLEDGE_FIELDS[filename].get(parent)
        assert parent_rule is not None, f"{key} names a parent '{parent}' that is not classified"
        assert parent_rule[0] == "applied", (
            f"{key} is reached by iterating '{parent}', but '{parent}' is {parent_rule[0]}, "
            f"so nothing actually iterates it"
        )

    @pytest.mark.parametrize("filename,key,parent", CASES)
    def test_key_really_hangs_off_that_parent(self, filename, key, parent):
        assert _declared_keys(filename).get(key) == parent, (
            f"{key} is registered as dynamic under '{parent}' but does not appear there"
        )


class TestLoaderFunctionsHaveCallers:
    """A field read only by the loader is still inert if nothing calls the loader function.

    This is the re-forking case the old guard could not see: `crawler_tools` could drop its
    `knowledge.policy_url_patterns()` call, hardcode the list again, and the field would still
    look read because `knowledge.py` itself accesses it.
    """

    @staticmethod
    def _public_functions() -> list[str]:
        tree = ast.parse(_LOADER.read_text(encoding="utf-8"))
        return [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]

    @staticmethod
    def _callers(func: str) -> list[str]:
        hits = []
        for path in _BACKEND.rglob("*.py"):
            if "__pycache__" in path.parts or "tests" in path.parts or path == _LOADER:
                continue
            if f"{func}(" in path.read_text(encoding="utf-8"):
                hits.append(str(path))
        return hits

    @pytest.mark.parametrize("func", _public_functions.__func__())
    def test_every_loader_function_is_called(self, func):
        # applied()/display()/dynamic() build the registry and are called by this test module.
        if func in {"applied", "display", "dynamic"}:
            pytest.skip("registry constructor, consumed by the test suite")
        assert self._callers(func), (
            f"knowledge.{func}() has no caller outside the loader, so the fields it reads are "
            f"inert. Either wire it up or delete it."
        )
