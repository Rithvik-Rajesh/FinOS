"""Architecture-boundary tests — structural rules enforced in CI.

These encode the two load-bearing invariants from ARCHITECTURE.md:

1. Only `app.modules.ai` may import `app.llm` (AI-optionality wall, ADR-005).
2. `app.domain` is pure — it must not import I/O layers (db, llm, api, modules).

If these fail, a boundary the whole design depends on has been crossed.
"""

from __future__ import annotations

import ast
import pathlib

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _py_files(*parts: str) -> list[pathlib.Path]:
    base = APP_ROOT.joinpath(*parts)
    return list(base.rglob("*.py")) if base.exists() else []


def test_only_ai_module_imports_llm() -> None:
    offenders: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        rel = path.relative_to(APP_ROOT)
        if rel.parts[:2] == ("modules", "ai"):
            continue
        if any(imp == "app.llm" or imp.startswith("app.llm.") for imp in _imports(path)):
            offenders.append(str(rel))
    assert not offenders, f"app.llm imported outside modules/ai: {offenders}"


def test_domain_is_pure() -> None:
    forbidden = ("app.db", "app.llm", "app.api", "app.modules", "app.workers")
    offenders: list[str] = []
    for path in _py_files("domain"):
        for imp in _imports(path):
            if any(imp == f or imp.startswith(f + ".") for f in forbidden):
                offenders.append(f"{path.name} -> {imp}")
    assert not offenders, f"domain/ must stay pure, found: {offenders}"
