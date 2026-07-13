"""Python port of the ``@pca/shared`` forbidden-field scanner (Task 28.1).

The public-privacy gate's term lists live in ONE place:
``packages/shared/src/public/forbidden-fields.ts``. The shared package's
``generate`` script serializes them to the gitignored build artifact
``packages/shared/generated/forbidden-fields.json`` (the ``@pca/taxonomy``
``taxonomy.json`` pattern — root ``pnpm generate`` emits both, and CI's
Python job already runs it before pytest). This module loads that artifact
and ports the ~30-line scan walk from
``packages/shared/src/forbidden-scan.ts``, so aggregate rows written by
Python are checked against the SAME stems and value patterns the API and
E2E privacy suites enforce — a hand-copied Python term list can never
drift, because there isn't one.

Port semantics (kept behavior-identical to the TS scanner):

- Keys are normalized (lowercased, ``_`` and ``-`` stripped) and flagged
  when the normalized form CONTAINS any stem.
- Every string value is tested against every value pattern. The shared
  patterns deliberately use only regex constructs whose semantics match
  between JavaScript and Python ``re`` (``\\b``, ``(?:)``, ``\\d``,
  character classes, bounded repetition, the ``i`` flag); an artifact
  pattern carrying an unsupported flag is a hard load failure, never a
  silently weaker scan. (Python's Unicode ``\\d`` is a superset of JS's
  ASCII ``\\d`` — for a privacy gate, matching more only errs safe.)
- Violations are returned, never raised, so callers own the failure
  handling. Callers under console-hygiene rules must report counts and
  check codes only — a violation's ``offender`` value is by definition
  suspect and must never be printed or logged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_ARTIFACT_RELPATH = ("packages", "shared", "generated", "forbidden-fields.json")

# JS RegExp flag -> Python re flag. Only flags actually representable in both
# engines are accepted; anything else fails the load loudly.
_FLAG_MAP = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
}


@dataclass(frozen=True)
class ForbiddenTerms:
    """The loaded scanner inputs: normalized key stems + compiled value patterns."""

    field_stems: tuple[str, ...]
    value_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class ForbiddenViolation:
    """One forbidden-content hit; mirrors the TS ``ForbiddenViolation`` shape.

    ``offender`` (the raw key name or matching string value) exists for
    assertion messages in tests over synthetic data ONLY — production
    callers must never print or log it.
    """

    json_path: str
    kind: Literal["key", "value"]
    offender: str
    matched: str


def _compile_pattern(source: str, flags: str) -> re.Pattern[str]:
    re_flags = 0
    for flag in flags:
        mapped = _FLAG_MAP.get(flag)
        if mapped is None:
            raise ValueError(
                f"forbidden-fields.json value pattern uses JS regex flag {flag!r} "
                "with no Python equivalent; the shared pattern list must stay "
                "portable (see packages/shared/src/generate.ts)"
            )
        re_flags |= mapped
    return re.compile(source, re_flags)


def load_forbidden_terms(path: Path | None = None) -> ForbiddenTerms:
    """Load the shared forbidden-field artifact into scanner inputs.

    With ``path`` omitted, walks up from this module to find
    ``packages/shared/generated/forbidden-fields.json`` (the taxonomy-loader
    pattern). Raises ``FileNotFoundError`` with a ``pnpm generate`` hint if
    the artifact is missing, and ``ValueError`` on an empty stem list or an
    unportable pattern flag — a degenerate artifact must never scan as
    "clean".
    """
    if path is None:
        here = Path(__file__).resolve()
        for candidate in here.parents:
            probe = candidate.joinpath(*_ARTIFACT_RELPATH)
            if probe.is_file():
                path = probe
                break
        if path is None:
            raise FileNotFoundError(
                "forbidden-fields.json not found; run `pnpm generate` to build "
                "packages/shared/generated/forbidden-fields.json"
            )
    data = json.loads(path.read_text())
    stems = tuple(str(stem) for stem in data["fieldStems"])
    if not stems:
        raise ValueError(
            "forbidden-fields.json carries no field stems; refusing a scanner "
            "that cannot flag anything"
        )
    patterns = tuple(
        _compile_pattern(str(entry["source"]), str(entry["flags"]))
        for entry in data["valuePatterns"]
    )
    return ForbiddenTerms(field_stems=stems, value_patterns=patterns)


def _normalize_key(key: str) -> str:
    """Casing/separator normalization, byte-for-byte the TS ``normalizeKey``."""
    return key.lower().replace("_", "").replace("-", "")


def scan_for_forbidden(body: object, terms: ForbiddenTerms) -> list[ForbiddenViolation]:
    """Deep-recursive scan of a JSON-shaped value (dicts, lists, scalars).

    Returns every violation rather than raising, mirroring the TS
    ``scanForForbidden`` walk: dict keys are stem-checked, string values are
    pattern-checked, lists/dicts recurse with a JSON-path trail.
    """
    violations: list[ForbiddenViolation] = []
    _walk(body, "$", terms, violations)
    return violations


def _walk(
    node: object,
    path: str,
    terms: ForbiddenTerms,
    violations: list[ForbiddenViolation],
) -> None:
    if isinstance(node, str):
        for pattern in terms.value_patterns:
            if pattern.search(node):
                violations.append(
                    ForbiddenViolation(
                        json_path=path,
                        kind="value",
                        offender=node,
                        matched=pattern.pattern,
                    )
                )
        return

    if isinstance(node, list | tuple):
        for index, item in enumerate(node):
            _walk(item, f"{path}[{index}]", terms, violations)
        return

    if isinstance(node, dict):
        for key, value in node.items():
            key_path = f"{path}.{key}"
            normalized = _normalize_key(str(key))
            for stem in terms.field_stems:
                if stem in normalized:
                    violations.append(
                        ForbiddenViolation(
                            json_path=key_path,
                            kind="key",
                            offender=str(key),
                            matched=stem,
                        )
                    )
            _walk(value, key_path, terms, violations)
