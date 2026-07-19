# Runbook: Rollback and Republish-to-Prod (Phase 31)

Recovery and refresh procedures per ADR 0004 Decision 10. Same standing
rules as the other runbooks: verbatim output capture, production
`DATABASE_URL` only ever via `read -s` (never in a file, never echoed,
never on a command line).

---

## Rollback

### R1 — Code rollback (web or API)

Render dashboard → the affected service → Deploys → Rollback to the last
known-good deploy. Web and API roll back independently; if an API contract
change is involved, roll back BOTH to the paired deploys from the same
`main` commit.

**Checkpoint:** service healthy on the rolled-back deploy; one result page
renders over the domain; `data-coverage` still reports `"available":true`.

### R2 — Data rollback

Production data is a disposable mirror; canonical truth is the local `pca`
database plus the local court-data artifacts. Recovery = re-run the
republish procedure below from the local source. There is nothing to
salvage from the production side — never edit production data in place.

### R3 — Edge hold / point-away

If the site must go dark quickly: Cloudflare → the DNS record → disable
proxy and point away (or use an emergency block rule on `/*`). This is the
fastest lever and reverses instantly.

**Checkpoint:** domain no longer serves the app; Render services untouched
(they recover by re-pointing DNS).

---

## Republish-to-prod

Re-runs the go-live fourteen-table dump/restore against a production database
that already contains data. The restore is data-only, so the existing rows
must be cleared first — one multi-table TRUNCATE handles the foreign keys
because all fourteen tables are truncated together.

1. Produce/refresh the local publish (the normal local pipeline flow:
   generate → validate → publish; never on Render, never with `CI` set).
2. Dump the fourteen tables and build the FK-ordered TOC exactly as in
   `docs/runbook-go-live.md` Step 4 (items 1–2).
3. Clear and restore:

   ```sh
   read -s PROD_DATABASE_URL
   export PROD_DATABASE_URL
   psql "$PROD_DATABASE_URL" -c 'truncate
     ref.normalized_charges, ref.charge_aliases,
     ref.normalized_judges, ref.judge_aliases,
     analytics.aggregate_runs,
     analytics.charge_outcome_aggregates,
     analytics.charge_sentencing_aggregates,
     analytics.judge_outcome_aggregates,
     analytics.judge_sentencing_aggregates,
     analytics.charge_sentencing_index_summaries,
     analytics.charge_sentencing_index_aggregates,
     analytics.charge_conviction_grade_aggregates,
     analytics.judge_sentencing_index_summaries,
     analytics.judge_sentencing_index_aggregates;'
   pg_restore --single-transaction --data-only \
     -L /tmp/toc.ordered \
     -d "$PROD_DATABASE_URL" \
     /tmp/pca-public-14table.dump
   rm /tmp/pca-public-14table.dump /tmp/toc.full /tmp/toc.ordered
   unset PROD_DATABASE_URL
   ```

   Between the TRUNCATE and the restore completing there is a brief window
   where the public app serves its 200-unavailable arms (`"available":false`
   on data-coverage) — expected and self-healing; the keyword monitor may
   flag it if the window crosses a poll.

**Checkpoint:** `pg_restore` exits 0 (single transaction — partial states
impossible); the go-live Step 4 per-table count comparison passes at run
time; `https://<domain>/api/v1/public/data-coverage` reports
`"available":true` with the refreshed `lastRefreshed` timestamp; one result
page renders.

Never run `db:seed`, the migrator with pending untested migrations, or any
pipeline command against the production URL as part of this procedure. The
migrator runs against production only when a new merged migration
accompanies a release, and then before the dump/restore.
