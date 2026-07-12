"""Judge-roster loader guard test (Task 22.3).

The loader touches the DB, so the only tier-1-safe behavior to assert is the CI
refusal (existing 21.3 guard pattern). The happy-path DB read + fake-judge
exclusion is exercised end-to-end by the acceptance coverage run over real data,
reported verbatim.
"""

from __future__ import annotations

import pytest

from pipeline.normalization.judge_roster_loader import (
    CIExecutionError,
    load_judge_roster,
)


def test_loader_refuses_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "1")
    with pytest.raises(CIExecutionError):
        load_judge_roster("postgresql://unused")


def test_loader_refuses_under_github_actions(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(CIExecutionError):
        load_judge_roster("postgresql://unused")
