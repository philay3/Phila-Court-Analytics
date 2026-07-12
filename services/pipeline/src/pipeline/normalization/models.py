"""Normalization result models (Task 22.1).

Frozen dataclasses (pinned decision 1): immutability matches the
fact-row/parsed-row conventions, and construction-time validation makes invalid
states UNREPRESENTABLE rather than flagged later. Every contract in pinned
decisions 2-4 (and 7 for money) is enforced in ``__post_init__``; a violation
raises ``ValueError`` at construction.

Four normalization result models share one validated base (identical fields and
rules; distinct types so 22.2/22.3/22.4 matchers return domain-specific
results):

- :class:`ChargeNormalizationResult`
- :class:`JudgeNormalizationResult`
- :class:`OutcomeNormalizationResult`
- :class:`SentencingNormalizationResult`

plus the standalone :class:`MoneyExtractionResult` (pinned decision 7).

Warnings on a result are a ``tuple[str, ...]`` of codes drawn ONLY from
``NORM_WARNING_CODES`` — no structural-context dicts here (that context lives on
the review-item locator). ``review_needed`` is derived-by-default: pass it and
it is validated against the map; omit it (``None``) and it is derived and set.

NO DB access, NO psycopg: these models are pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.normalization.vocab import (
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHODS,
    MATCHED_METHODS,
    NORM_WARNING_CODES,
    derive_review_needed,
)


@dataclass(frozen=True)
class NormalizationCandidate:
    """One candidate identity for an ambiguous match (structural only).

    Carries the normalized id and its display name — never raw docket text or
    defendant-identifying content.
    """

    normalized_id: str
    display_name: str

    def __post_init__(self) -> None:
        if not self.normalized_id:
            raise ValueError("candidate normalized_id must be non-empty")
        if not self.display_name:
            raise ValueError("candidate display_name must be non-empty")


@dataclass(frozen=True)
class _NormalizationResult:
    """Shared, validated base for the four normalization result models.

    Fields (acceptance criterion 1):

    - ``raw_value`` — the value that was normalized (present always).
    - ``match_method`` — one of the locked six ``MATCH_METHODS``.
    - ``normalized_id`` / ``display_name`` — the normalized identity, present
      iff ``match_method`` is a matched method (pinned decision 4).
    - ``warnings`` — a tuple of codes from ``NORM_WARNING_CODES``.
    - ``candidates`` — >= 2 candidates iff ``ambiguous``, empty otherwise
      (pinned decision 3).
    - ``review_needed`` — derived-by-default (see below).

    ``review_needed`` is ``bool | None``: when ``None`` (the default), it is
    derived via :func:`derive_review_needed` and set; when explicitly passed, it
    must equal the derived value or construction raises. This lets 22.2/22.3
    matchers omit it and inherit the single derivation, while still catching a
    caller that hand-computes a disagreeing value.
    """

    raw_value: str
    match_method: str
    normalized_id: str | None = None
    display_name: str | None = None
    warnings: tuple[str, ...] = ()
    candidates: tuple[NormalizationCandidate, ...] = ()
    review_needed: bool | None = None

    def __post_init__(self) -> None:
        # Pinned decision 2: method vocabulary is closed.
        if self.match_method not in MATCH_METHODS:
            raise ValueError(f"unknown match method: {self.match_method!r}")

        # Acceptance criterion 4: warning vocabulary is closed.
        for code in self.warnings:
            if code not in NORM_WARNING_CODES:
                raise ValueError(f"unknown normalization warning code: {code!r}")

        is_matched = self.match_method in MATCHED_METHODS

        # Pinned decision 4: normalized identity present iff matched method.
        if is_matched:
            if self.normalized_id is None or self.display_name is None:
                raise ValueError(
                    "matched result requires normalized_id and display_name"
                )
        else:
            if self.normalized_id is not None or self.display_name is not None:
                raise ValueError(
                    f"{self.match_method!r} result must not carry a normalized identity"
                )

        # Pinned decision 3: candidate-list rule is structural.
        if self.match_method == MATCH_METHOD_AMBIGUOUS:
            if len(self.candidates) < 2:
                raise ValueError("ambiguous result requires >= 2 candidates")
        else:
            if self.candidates:
                raise ValueError(
                    f"{self.match_method!r} result must not carry candidates"
                )

        # Pinned decision 6: review_needed is derived-by-default; a passed value
        # must equal the derived one.
        derived = derive_review_needed(self.match_method, self.warnings)
        if self.review_needed is None:
            object.__setattr__(self, "review_needed", derived)
        elif self.review_needed != derived:
            raise ValueError(
                f"review_needed={self.review_needed!r} disagrees with derived "
                f"value {derived!r}"
            )


@dataclass(frozen=True)
class ChargeNormalizationResult(_NormalizationResult):
    """Charge normalization result (22.2 charge matcher returns this)."""


@dataclass(frozen=True)
class JudgeNormalizationResult(_NormalizationResult):
    """Judge normalization result (22.3 judge matcher returns this)."""


@dataclass(frozen=True)
class OutcomeNormalizationResult(_NormalizationResult):
    """Outcome (disposition) normalization result (22.4 mapping returns this)."""


@dataclass(frozen=True)
class SentencingNormalizationResult(_NormalizationResult):
    """Sentencing-component normalization result (22.4 mapping returns this)."""


@dataclass(frozen=True)
class MoneyExtractionResult:
    """Monetary amount extraction result (pinned decision 7).

    Integer cents only — floats are prohibited everywhere in the money path
    (SD 10 extractor lands with 22.4; this is the model only, no parsing here).
    ``amount_cents`` is a real ``int`` or ``None``; a ``float`` (or ``bool``,
    which is an ``int`` subclass) raises at construction. ``warnings`` are codes
    from ``NORM_WARNING_CODES``.
    """

    raw_text: str
    amount_cents: int | None = None
    warnings: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.amount_cents is not None:
            # bool is an int subclass; reject it and every non-int (floats) so
            # integer cents is the only representable numeric form.
            if isinstance(self.amount_cents, bool) or not isinstance(
                self.amount_cents, int
            ):
                raise ValueError(
                    "amount_cents must be an int number of cents or None; "
                    f"got {type(self.amount_cents).__name__}"
                )
        for code in self.warnings:
            if code not in NORM_WARNING_CODES:
                raise ValueError(f"unknown normalization warning code: {code!r}")
