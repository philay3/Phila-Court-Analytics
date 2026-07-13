"""Publish a validated aggregate run, invalidating the prior published run (Task 28.2).

The publication step of the Sprint 6 lifecycle (SD 3 — generation, validation,
and publication are separate steps; publish is an explicit command, never
automatic after validation). ``pipeline publish-aggregates`` points at a
VALIDATED run (``status='completed'``, ``published_at``/``invalidated_at``
NULL — the 26.1 vocabulary mapping; no new status values, no migration) and,
in ONE transaction:

- sets ``invalidated_at`` + ``invalidated_reason`` on the currently active
  published run (the §6.3 predicate: ``published_at IS NOT NULL AND
  invalidated_at IS NULL``), if one exists and it is not the target — the
  prior run is invalidated, NEVER deleted, and remains a rollback target;
- sets ``published_at`` on the target run.

Invalidate-before-publish ordering keeps the partial unique index
(``aggregate_runs_active_published_idx``, at most one active published run)
satisfied statement-by-statement. The ``aggregate_runs_published_at_check``
DB constraint (``published_at IS NULL OR status='completed'``) structurally
backstops the status guard here — an unvalidated run cannot be published even
by hand.

Idempotent: re-running against a run that is already published and still
active is a no-op success. Failed, invalidated, and superseded (published but
already invalidated) runs are refused — republishing an invalidated run would
resurrect superseded data. A bare re-run (no ``--run``) never demotes newer
published data either: a default candidate validated BEFORE the active
published run is refused as stale (``StaleValidatedRunError``); publishing an
older run over a newer one requires an explicit ``--run``.

Numbers discipline: nothing here pins a figure from any prior run — publish
operates on whatever run it is pointed at.

Console/log output is statuses and hash-prefix run ids only.
``DATABASE_URL`` is read at the CLI boundary (21.3 pattern), never here.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("pipeline.aggregates.publish")

# Lifecycle status strings (26.1 adjudicated mapping; see generate.py).
PUBLISHABLE_STATUS = "completed"


class NoValidatedRunError(RuntimeError):
    """No validated (completed, unpublished) aggregate run exists (STOP)."""


class RunNotPublishableError(RuntimeError):
    """A ``--run`` id that is absent, unvalidated, failed, or invalidated (STOP)."""


class StaleValidatedRunError(RuntimeError):
    """The default target was validated before the active published run (STOP).

    Without this guard a bare re-run after a successful publish is NOT a
    no-op when an older validated-unpublished run is still lying around: the
    default resolution would pick that leftover and silently supersede the
    newer published data with older data. Replacing an active run with an
    earlier-validated one must be an explicit ``--run`` decision.
    """


def invalidation_reason(published_run_id: str) -> str:
    """The ``invalidated_reason`` written onto the run a publish supersedes."""
    return f"superseded by publish of run {published_run_id}"


def _resolve_run(conn: psycopg.Connection, run_id: str | None) -> dict[str, object]:
    """Resolve the run to publish, returning its lifecycle row.

    Default: the latest validated run (``completed``, unpublished,
    uninvalidated) — refused if it was validated BEFORE the currently active
    published run (see ``StaleValidatedRunError``). ``--run`` forces a
    specific id, which must be ``completed`` and uninvalidated (the stale
    guard does not apply: an explicit id is operator intent); an
    already-published-and-active target is allowed through for the idempotent
    no-op path.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        if run_id is not None:
            cur.execute(
                "SELECT id, status, published_at, invalidated_at "
                "FROM analytics.aggregate_runs WHERE id = %s",
                (run_id,),
            )
            row = cur.fetchone()
            if (
                row is None
                or row["status"] != PUBLISHABLE_STATUS
                or row["invalidated_at"] is not None
            ):
                raise RunNotPublishableError(
                    "requested --run is not a publishable (validated, "
                    "uninvalidated) aggregate run"
                )
            return row
        cur.execute(
            "SELECT id, status, published_at, invalidated_at, completed_at "
            "FROM analytics.aggregate_runs "
            "WHERE status = %s AND published_at IS NULL "
            "AND invalidated_at IS NULL "
            "ORDER BY completed_at DESC LIMIT 1",
            (PUBLISHABLE_STATUS,),
        )
        row = cur.fetchone()
        if row is None:
            raise NoValidatedRunError(
                "no validated (unpublished) aggregate run exists; run "
                "`pipeline validate-aggregates` first"
            )
        cur.execute(
            "SELECT completed_at FROM analytics.aggregate_runs "
            "WHERE published_at IS NOT NULL AND invalidated_at IS NULL"
        )
        active = cur.fetchone()
        if (
            active is not None
            and active["completed_at"] is not None
            and row["completed_at"] is not None
            and active["completed_at"] > row["completed_at"]
        ):
            raise StaleValidatedRunError(
                "the latest validated (unpublished) run was validated before "
                "the active published run; refusing to replace newer "
                "published data by default — pass --run to publish it "
                "explicitly"
            )
        return row


def publish_aggregates(conn: psycopg.Connection, *, run_id: str | None) -> int:
    """Publish one validated run, invalidating the prior active run atomically.

    Returns 0 on success (including the idempotent already-published no-op),
    2 on a STOP (no run to publish / non-publishable ``--run``).
    """
    try:
        target = _resolve_run(conn, run_id)
    except (
        NoValidatedRunError,
        RunNotPublishableError,
        StaleValidatedRunError,
    ) as exc:
        logger.error(
            "refusing to publish aggregates", extra={"reason": type(exc).__name__}
        )
        return 2

    target_id = str(target["id"])

    # Idempotent no-op: the target is already the active published run.
    if target["published_at"] is not None:
        print(f"publish-aggregates run={target_id[:16]} already published; no-op")
        logger.info("aggregate run already published", extra={"run": target_id[:16]})
        return 0

    now = datetime.now(UTC)
    with conn.transaction():
        with conn.cursor(row_factory=dict_row) as cur:
            # Lock the active published row (§6.3 predicate) so a concurrent
            # publish cannot interleave between invalidate and publish.
            cur.execute(
                "SELECT id FROM analytics.aggregate_runs "
                "WHERE published_at IS NOT NULL AND invalidated_at IS NULL "
                "FOR UPDATE"
            )
            prior = cur.fetchone()
            prior_id = str(prior["id"]) if prior is not None else None
            if prior_id is not None:
                # Invalidated, never deleted: the prior run (the seeded run,
                # on first real publish) stays as a rollback target.
                cur.execute(
                    "UPDATE analytics.aggregate_runs "
                    "SET invalidated_at = %s, invalidated_reason = %s "
                    "WHERE id = %s",
                    (now, invalidation_reason(target_id), prior_id),
                )
            cur.execute(
                "UPDATE analytics.aggregate_runs SET published_at = %s WHERE id = %s",
                (now, target_id),
            )

    print(f"publish-aggregates run={target_id[:16]} published")
    if prior_id is not None:
        print(f"prior published run {prior_id[:16]} invalidated (superseded)")
    else:
        print("no prior published run to invalidate")
    logger.info(
        "aggregate run published",
        extra={
            "run": target_id[:16],
            "invalidated": prior_id[:16] if prior_id else None,
        },
    )
    return 0


def run_publish_aggregates(database_url: str, *, run_id: str | None) -> int:
    """CLI entry: connect and publish (DATABASE_URL read at the CLI boundary)."""
    from pipeline import db

    with db.connect(database_url) as conn:
        return publish_aggregates(conn, run_id=run_id)
