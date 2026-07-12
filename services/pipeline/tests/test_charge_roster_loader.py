"""Charge-roster loader guard test (Task 22.2, AC 5).

The loader touches the DB, so the only tier-1-safe behavior to assert is the CI
refusal (existing 21.3 guard pattern). The happy-path DB read is exercised
end-to-end by the acceptance coverage run over real data, reported verbatim.
"""

from __future__ import annotations

import pytest

from pipeline.normalization.charge_roster_loader import (
    CIExecutionError,
    load_charge_roster,
)


def test_loader_refuses_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "1")
    # Refuses before any connection attempt, so the URL is never used.
    with pytest.raises(CIExecutionError):
        load_charge_roster("postgresql://unused")


def test_loader_refuses_under_github_actions(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(CIExecutionError):
        load_charge_roster("postgresql://unused")
