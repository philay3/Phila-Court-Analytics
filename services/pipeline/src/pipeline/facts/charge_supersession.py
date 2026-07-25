"""Charge supersession — the MC→CP double-count fix (operator ruling 2026-07-25).

A charge held for court in Municipal Court continues as the SAME charge on a
Court of Common Pleas case; counting both rows inflates every volume-style
number. This module derives ``parsed.charges.superseded_by_charge_id``: the MC
held charge points at the CP charge it continues as, and every volume-style
count filters ``WHERE superseded_by_charge_id IS NULL``.

THE JOIN IS DETERMINISTIC — verified by the operator against real CP/MC docket
pairs. All conditions required, nothing fuzzy:

  Case level:    CP.originating_docket_no = MC.docket_number
                 AND CP.otn = MC.otn          (whitespace/case-folded equality)
  Charge level:  CP.orig_seq = MC.sequence
                 AND statute match            (canonical citation equality)

plus two guards:

  * The MC charge's CURRENT disposition is a held form (the 22.4 mapper is the
    single authority). Charges withdrawn/dismissed at the preliminary hearing
    never get a CP copy and keep their real terminal MC outcomes; a charge
    held, remanded, and dismissed reads its LATEST disposition (the parser
    keys the last routed disposition event), so it can never be superseded.
  * One pointer per MC charge. If two CP cases claim the same MC charge (a
    remand/refile second round of proceedings), the LATEST-FILED CP case wins
    (filed_date, then docket_number, then charge id — fully deterministic);
    and one CP charge absorbs at most one MC charge (its single orig_seq).

Untraced held charges keep counting on the MC side. That bucket includes time
lag — a proceeding charge whose CP case has not been filed or collected yet —
and resolves on future refreshes; a shrinking untraced count is expected, not
a defect. The fetch list for uncollected CP targets remains
``SELECT DISTINCT target_docket_number FROM parsed.docket_links WHERE
target_docket_id IS NULL``.

Lifecycle: the mapping is DERIVED state, re-derived whole on every fact build
(clear all pointers, re-point from the join — idempotent on an unchanged
corpus) and standalone via ``pipeline backfill-charge-supersession``. The
pointer column is the parsed layer's single update-writable column
(operator-ruled deviation from the load-artifact contract, documented at the
migration and the Kysely type). Nothing here touches fact eligibility: outcome
facts already count only the CP side, so served percentages are unchanged by
construction.

Console hygiene: counts only — never docket numbers, OTNs, or charge text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date

import psycopg
from psycopg.rows import dict_row

from pipeline.normalization.charge_matcher import canonicalize_statute
from pipeline.normalization.outcome_mapper import OutcomeMapper

# The CP/MC court types as recorded in parsed.dockets.court_type_derived.
_CP_COURT_TYPE = "CP"
_MC_COURT_TYPE = "MC"

_WHITESPACE = re.compile(r"\s+")

# Sort placeholder for NULL filed dates (they order last under the reverse
# sort; the boolean leg of the key is what actually separates them).
_DATE_FLOOR = date.min


def _fold_otn(value: object) -> str | None:
    """OTN equality key: uppercase, whitespace collapsed. None stays None."""
    if value is None:
        return None
    folded = _WHITESPACE.sub(" ", str(value)).strip().upper()
    return folded if folded else None


def _fold_docket_number(value: object) -> str | None:
    """Docket-number equality key: uppercase, stripped. None stays None."""
    if value is None:
        return None
    folded = str(value).strip().upper()
    return folded if folded else None


def _load_cp_claims(conn: psycopg.Connection) -> list[dict[str, object]]:
    """Every CP charge that names an MC origin: one candidate claim per row.

    A claim = (originating docket number, OTN, orig_seq, statute) plus the CP
    docket's filed date for latest-filed-wins ordering. Rows missing any join
    ingredient are excluded here — every condition is required.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.id AS cp_charge_id, c.orig_seq, c.statute,
                   d.docket_number AS cp_docket_number,
                   d.originating_docket_no, d.otn, d.filed_date
            FROM parsed.charges c
            JOIN parsed.dockets d ON d.id = c.docket_id
            WHERE d.court_type_derived = %s
              AND d.originating_docket_no IS NOT NULL
              AND d.otn IS NOT NULL
              AND c.orig_seq IS NOT NULL
              AND c.statute IS NOT NULL
            """,
            (_CP_COURT_TYPE,),
        )
        return list(cur.fetchall())


def _load_mc_targets(
    conn: psycopg.Connection, docket_numbers: list[str]
) -> dict[tuple[str, str], list[dict[str, object]]]:
    """MC charges on the named originating dockets, keyed by (docket_no, otn).

    Only dockets whose (folded) docket number is actually claimed are loaded.
    A docket number appearing on more than one MC docket rides through as
    multiple entries under its (docket_no, otn) key — the OTN condition is
    what disambiguates, exactly as the operator specified.
    """
    targets: dict[tuple[str, str], list[dict[str, object]]] = {}
    if not docket_numbers:
        return targets
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.id AS mc_charge_id, c.sequence, c.statute,
                   c.disposition_raw, d.docket_number, d.otn
            FROM parsed.charges c
            JOIN parsed.dockets d ON d.id = c.docket_id
            WHERE d.court_type_derived = %s
              AND upper(d.docket_number) = ANY(%s)
              AND d.otn IS NOT NULL
            """,
            (_MC_COURT_TYPE, docket_numbers),
        )
        for row in cur.fetchall():
            docket_no = _fold_docket_number(row["docket_number"])
            otn = _fold_otn(row["otn"])
            if docket_no is None or otn is None:
                continue
            targets.setdefault((docket_no, otn), []).append(dict(row))
    return targets


def derive_supersessions(
    conn: psycopg.Connection, *, mapper: OutcomeMapper
) -> tuple[dict[str, str], dict[str, int]]:
    """Compute the full MC-charge → CP-charge supersession mapping (no writes).

    Returns ``(mapping, counts)`` where ``mapping`` is
    ``{mc_charge_id: cp_charge_id}``. Deterministic: claims are processed in
    (filed_date DESC, docket_number DESC, charge id) order so the latest-filed
    CP case wins any multi-claim, and each CP charge absorbs at most one MC
    charge.
    """
    claims = _load_cp_claims(conn)

    counts: dict[str, int] = {
        "cp_claims": len(claims),
        "superseded": 0,
        "no_case_match": 0,
        "no_seq_match": 0,
        "statute_mismatch": 0,
        "mc_not_currently_held": 0,
        "later_claim_won": 0,
        "cp_charge_already_used": 0,
    }

    claimed_numbers = sorted(
        {
            n
            for claim in claims
            if (n := _fold_docket_number(claim["originating_docket_no"])) is not None
        }
    )
    mc_targets = _load_mc_targets(conn, claimed_numbers)

    def is_held(row: Mapping[str, object]) -> bool:
        raw = row["disposition_raw"]
        return raw is not None and mapper.map(raw) is None  # type: ignore[arg-type]

    # Latest-filed CP case first; an earlier-filed claim on an already-pointed
    # MC charge loses (counted as later_claim_won). Three STABLE sorts build
    # the total order: charge id ASC (final tiebreak), docket number DESC,
    # filed date DESC with NULL filed dates last.
    ordered = sorted(claims, key=lambda c: str(c["cp_charge_id"]))
    ordered = sorted(
        ordered, key=lambda c: str(c["cp_docket_number"] or ""), reverse=True
    )
    ordered = sorted(
        ordered,
        key=lambda c: (c["filed_date"] is not None, c["filed_date"] or _DATE_FLOOR),
        reverse=True,
    )

    mapping: dict[str, str] = {}
    used_cp_charges: set[str] = set()

    for claim in ordered:
        docket_no = _fold_docket_number(claim["originating_docket_no"])
        otn = _fold_otn(claim["otn"])
        if docket_no is None or otn is None:
            counts["no_case_match"] += 1
            continue
        candidates = mc_targets.get((docket_no, otn))
        if not candidates:
            counts["no_case_match"] += 1
            continue

        claim_seq = int(claim["orig_seq"])  # type: ignore[arg-type]
        seq_matches = [c for c in candidates if int(c["sequence"]) == claim_seq]  # type: ignore[arg-type]
        if not seq_matches:
            counts["no_seq_match"] += 1
            continue

        cp_statute = canonicalize_statute(claim["statute"])  # type: ignore[arg-type]
        matched = [
            c
            for c in seq_matches
            if cp_statute and canonicalize_statute(c["statute"]) == cp_statute  # type: ignore[arg-type]
        ]
        if not matched:
            counts["statute_mismatch"] += 1
            continue

        # (docket_no, otn, sequence) is unique on real sheets; if versioned
        # duplicates ever coexist, charge id makes the pick deterministic.
        mc = min(matched, key=lambda c: str(c["mc_charge_id"]))
        mc_charge_id = str(mc["mc_charge_id"])
        cp_charge_id = str(claim["cp_charge_id"])

        if not is_held(mc):
            counts["mc_not_currently_held"] += 1
            continue
        if mc_charge_id in mapping:
            # A LATER-filed CP case already claimed this MC charge (we walk
            # latest-first), e.g. a remand/refile second round.
            counts["later_claim_won"] += 1
            continue
        if cp_charge_id in used_cp_charges:
            counts["cp_charge_already_used"] += 1
            continue

        mapping[mc_charge_id] = cp_charge_id
        used_cp_charges.add(cp_charge_id)
        counts["superseded"] += 1

    return mapping, counts


def run_backfill_charge_supersession(conn: psycopg.Connection) -> int:
    """CLI entry: derive + apply the mapping, then print the verification view.

    The backfill is the same derivation every fact build runs — standalone so
    the operator can point it at the current corpus right after the v3 reload
    without waiting for a build. Output is counts and public roster slugs
    only. The retail-theft line is the operator's pinned sanity check.
    """
    from pipeline.normalization.outcome_mapper import load_taxonomy_snapshot

    mapper = OutcomeMapper(load_taxonomy_snapshot())
    mapping, counts = derive_supersessions(conn, mapper=mapper)
    with conn.transaction():
        applied = apply_supersessions(conn, mapping)

    print("backfill-charge-supersession:")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")
    print(f"  pointers_written: {applied}")

    # Verification preview — the volume math over the corpus as now pointed.
    # Local import: the aggregates layer sits above facts; this is an operator
    # verification aid inside a CLI runner, not a module-level dependency.
    from pipeline.aggregates.volume import (
        build_charge_volume_rows,
        load_charge_warning_codes,
        load_volume_corpus,
        preview_by_slug,
    )
    from pipeline.normalization.charge_matcher import ChargeMatcher
    from pipeline.normalization.charge_roster_loader import (
        load_charge_roster_from_connection,
    )

    roster = load_charge_roster_from_connection(conn)
    matcher = ChargeMatcher(roster)
    slug_by_id = {entry.normalized_id: entry.slug for entry in roster.entries}
    rows, report = build_charge_volume_rows(
        load_volume_corpus(conn),
        load_charge_warning_codes(conn),
        matcher=matcher,
        mapper=mapper,
        taxonomy_version="preview",
    )
    print(
        f"volume preview: universe_rows={report['rows_in_universe']} "
        f"superseded_folded={report['superseded_folded']} "
        f"volume_rows={report['volume_rows']}"
    )
    print("top slugs by folded volume:")
    for line in preview_by_slug(rows, slug_by_id):
        print(line)
    retail = next(
        (r for r in rows if slug_by_id.get(str(r["charge_id"])) == "retail-theft"),
        None,
    )
    if retail is not None:
        print(
            "retail-theft sanity line: "
            f"seen={retail['charges_seen']} "
            f"outcomes={retail['outcomes_recorded']} "
            f"held_untraced={retail['held_for_court']} "
            f"pending={retail['still_pending']} "
            f"excluded={retail['disposed_excluded']} "
            f"folded_into_cp={retail['held_superseded']}"
        )
    else:
        print("retail-theft sanity line: no volume row (slug absent or zero journeys)")
    return 0


def apply_supersessions(conn: psycopg.Connection, mapping: Mapping[str, str]) -> int:
    """Clear every pointer and write the derived mapping (caller's transaction).

    Whole-mapping replacement keeps the column a pure projection of the
    current corpus + join logic: stale pointers from any earlier derivation
    cannot survive, and a re-run on an unchanged corpus is a net-zero change.
    Does not commit.
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE parsed.charges SET superseded_by_charge_id = NULL "
            "WHERE superseded_by_charge_id IS NOT NULL"
        )
        if mapping:
            cur.executemany(
                "UPDATE parsed.charges SET superseded_by_charge_id = %(cp)s "
                "WHERE id = %(mc)s",
                [{"mc": mc, "cp": cp} for mc, cp in sorted(mapping.items())],
            )
    return len(mapping)
