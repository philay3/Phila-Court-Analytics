"""The conviction outcome-category family (Task 35.1; Phase 35 design gate).

The SINGLE Python source for which outcome taxonomy codes constitute a
conviction. Every surface that needs the family imports this constant — the
inline pair appears nowhere else (Phase 35 gate pin). The codes are taxonomy
codes (``@pca/taxonomy`` taxonomy.json); adding a category here is a
plan-level decision, never a local edit.
"""

from __future__ import annotations

CONVICTION_OUTCOME_CATEGORIES: frozenset[str] = frozenset(
    {"guilty_plea", "guilty_verdict"}
)
