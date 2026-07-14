"""Whole-run fact pruning (`pipeline prune-fact-runs`, Task COL-4a).

The conscious operation the fact layer's RESTRICT FKs demand: fact.* -> parsed.*
deletes "must fail loudly; deleting the fact run first is a conscious operation"
(21.2 pinned decision). Docket supersession (COL-4a) and the same-hash
replace-newer arm both hit those FKs when fact rows still reference a parsed
graph; this command is the named remedy. The refresh ORDERING (prune -> refresh
-> load -> rebuild -> aggregate -> publish) is COL-4b runbook material — this
module only ships the tooling.

Runs are deleted WHOLE, never partially: one ``DELETE FROM fact.fact_build_runs``
per run, and the run's facts go via the build_run_id CASCADE (gate-verified:
``charge_outcomes.build_run_id`` and ``charge_sentences.build_run_id`` are the
only FKs into ``fact.*`` besides the internal ``charge_outcome_id``, all ON
DELETE CASCADE). Nothing else references ``fact.*`` — analytics.* FKs point only
to ``analytics.aggregate_runs`` and ``ref.*``, and ``review.queue_items`` carries
no fact FK — so published aggregates and review items are structurally
unaffected (AC-13).

Selection is explicit run ids OR ``--all-completed``, never both. Only
``completed`` runs are prunable: an ``in_progress`` id may be a live build and a
``failed`` id holds no facts (naming one is a mistake signal), so either refuses
the WHOLE invocation before any delete. An absent id is idempotent success
(``not_found`` — the goal state is already reached).

Destruction requires ``--confirm``: without it the command is a DRY RUN that
reports the selection and writes nothing. The whole invocation is one
transaction — any error rolls everything back; partial deletion is structurally
impossible.

Run-report files under ``~/court-data/reports/`` are the durable history; pruned
run rows are not a history loss (R3 adjudication). Console/log hygiene: counts,
statuses, and run-id short PREFIXES only (run UUIDs are synthetic surrogates,
never court-derived data).
"""

from __future__ import annotations

import logging

import psycopg

from pipeline.fact_review_vocab import RUN_COMPLETED

logger = logging.getLogger("pipeline.prune_fact_runs")

# Length of the run-id prefix printed in reports (hygiene: prefix ids only,
# matching the loader's 16-char source-hash prefixes).
_ID_PREFIX_LEN = 8


def _select_runs(
    conn: psycopg.Connection, run_ids: list[str], all_completed: bool
) -> tuple[list[tuple[str, str]], list[str]]:
    """Resolve the selection to ``([(run_id, status), ...], not_found_ids)``.

    ``--all-completed`` selects every ``completed`` run; explicit ids resolve
    against ``fact.fact_build_runs`` whatever their status (the caller enforces
    the completed-only rule so the refusal can name the offending status).
    """
    with conn.cursor() as cur:
        if all_completed:
            cur.execute(
                "SELECT id, status FROM fact.fact_build_runs "
                "WHERE status = %(status)s ORDER BY started_at",
                {"status": RUN_COMPLETED},
            )
            return [(str(r[0]), r[1]) for r in cur.fetchall()], []

        cur.execute(
            "SELECT id, status FROM fact.fact_build_runs WHERE id = ANY(%(ids)s)",
            {"ids": run_ids},
        )
        found = {str(r[0]): r[1] for r in cur.fetchall()}
    # Preserve invocation order; absent ids are idempotent success (not_found).
    selected = [(rid, found[rid]) for rid in run_ids if rid in found]
    not_found = [rid for rid in run_ids if rid not in found]
    return selected, not_found


def _count_facts(conn: psycopg.Connection, run_ids: list[str]) -> tuple[int, int]:
    """(outcome_count, sentence_count) for the selected runs, pre-delete."""
    if not run_ids:
        return 0, 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              (SELECT count(*) FROM fact.charge_outcomes
               WHERE build_run_id = ANY(%(ids)s)),
              (SELECT count(*) FROM fact.charge_sentences
               WHERE build_run_id = ANY(%(ids)s))
            """,
            {"ids": run_ids},
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0]), int(row[1])


def run_prune_fact_runs(
    conn: psycopg.Connection,
    *,
    run_ids: list[str],
    all_completed: bool,
    confirm: bool,
) -> int:
    """Prune the selected fact build runs whole; return the process exit code.

    Without ``--confirm``: dry run — print the selection (prefix ids + counts),
    write nothing, exit 0. With it: delete each selected run row in ONE
    transaction (facts go via the build_run_id CASCADE). A non-``completed``
    status among explicit ids refuses the whole invocation (exit 1, no writes);
    absent ids are counted ``not_found`` and the invocation still succeeds
    (idempotent, AC-13).
    """
    with conn.transaction():
        selected, not_found = _select_runs(conn, run_ids, all_completed)

        blocked = [(rid, status) for rid, status in selected if status != RUN_COMPLETED]
        if blocked:
            for rid, status in blocked:
                logger.error(
                    "refusing to prune a non-completed run; nothing deleted",
                    extra={"run": rid[:_ID_PREFIX_LEN], "status": status},
                )
            return 1

        selected_ids = [rid for rid, _ in selected]
        outcomes, sentences = _count_facts(conn, selected_ids)

        mode = "pruned" if confirm else "would_prune"
        for rid in selected_ids:
            logger.info(
                "run selected for prune",
                extra={"run": rid[:_ID_PREFIX_LEN], "mode": mode},
            )

        if confirm:
            with conn.cursor() as cur:
                # Whole-run delete: the run row goes, its facts go via CASCADE.
                cur.execute(
                    "DELETE FROM fact.fact_build_runs WHERE id = ANY(%(ids)s)",
                    {"ids": selected_ids},
                )
                assert cur.rowcount == len(selected_ids)

    print(
        f"{mode}={len(selected_ids)} not_found={len(not_found)} "
        f"outcomes_deleted={outcomes if confirm else 0} "
        f"sentences_deleted={sentences if confirm else 0} "
        f"outcomes_selected={outcomes} sentences_selected={sentences}"
    )
    if not confirm:
        logger.info("dry run: nothing deleted; pass --confirm to execute")
    return 0
