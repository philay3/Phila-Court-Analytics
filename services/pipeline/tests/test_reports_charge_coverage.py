"""Guard test for the charge-coverage report tool (Task 22.2, Required Fix 1b).

The coverage run reads local court data, so — like the distinct-value tool and
the roster loader — it must refuse to run in a CI environment before touching the
database. The report-building math is exercised end-to-end by the acceptance
coverage run over real data (reported verbatim); this asserts the CI guard.
"""

from __future__ import annotations

from pipeline.reports import charge_coverage
from pipeline.reports.charge_coverage import main


def test_main_refuses_in_ci(monkeypatch):
    monkeypatch.setattr(charge_coverage, "running_in_ci", lambda: True)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    assert main([]) == 2
