"""Prove the ported library modules are import-side-effect-free.

Capstone's identity module pulled in config.py, which read the environment
(os.getenv / load_dotenv) and created directories (Path.mkdir) at import
time. The ported modules must do none of that. Each module is evicted from
sys.modules and re-imported under guards that raise on any environment read
or filesystem mkdir, so the import genuinely re-executes the module body.
"""

import importlib
import os
import sys
from pathlib import Path

import pytest

MODULES = [
    "pipeline.helpers",
    "pipeline.identity",
    "pipeline.extraction",
    "pipeline.manual_import",
    "pipeline.seam_check",
    "pipeline.docket_parser",
    "pipeline.docket_parser_pdf",
    "pipeline.collector.enumeration",
    "pipeline.collector.classification",
    "pipeline.collector.guard",
    "pipeline.collector.engine",
    "pipeline.collector.transport",
    "pipeline.collector.run",
]

# Collector modules must import WITHOUT the optional Playwright dependency: the
# whole test suite and default install stay Playwright-free (Task COL-1).
COLLECTOR_MODULES = [m for m in MODULES if m.startswith("pipeline.collector.")]


@pytest.mark.parametrize("module_name", MODULES)
def test_import_has_no_env_or_fs_side_effects(module_name, monkeypatch):
    def _no_getenv(*args, **kwargs):
        raise AssertionError(f"import-time os.getenv call in {module_name}")

    def _no_mkdir(*args, **kwargs):
        raise AssertionError(f"import-time Path.mkdir call in {module_name}")

    monkeypatch.setattr(os, "getenv", _no_getenv)
    monkeypatch.setattr(Path, "mkdir", _no_mkdir)

    # Evict so the import genuinely re-executes the module body, not a
    # cached object; importlib.reload would run against the already-imported
    # module and would not prove a fresh import is clean.
    saved = sys.modules.pop(module_name, None)
    try:
        importlib.import_module(module_name)  # must not trip the guards
    finally:
        # Leave a normally-imported module in place for other tests.
        if saved is not None:
            sys.modules[module_name] = saved


@pytest.mark.parametrize("module_name", COLLECTOR_MODULES)
def test_collector_import_does_not_import_playwright(module_name):
    saved = sys.modules.pop(module_name, None)
    had_playwright = "playwright" in sys.modules
    sys.modules.pop("playwright", None)
    try:
        importlib.import_module(module_name)
        assert "playwright" not in sys.modules, (
            f"{module_name} imported Playwright at import time"
        )
    finally:
        if saved is not None:
            sys.modules[module_name] = saved
        if had_playwright:  # pragma: no cover - only if env had it preloaded
            import importlib as _il

            sys.modules["playwright"] = _il.import_module("playwright")
