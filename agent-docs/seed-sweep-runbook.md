# Seed-sweep runbook (task 29.1)

Operational steps for removing the fake/seeded rows from the live `pca`
database: the three fake seed judges, their aliases, and both registry
aggregate runs (the invalidated seeded published run and the unpublished
decoy) with all their aggregate rows. Demo charges and their aliases are
RETAINED (22.2 standing decision — real facts FK to them).

Targets are identified by the `db/seeds/` registry only, imported by the
tooling from the seed data modules:

- judge slugs (`JUDGE_SEEDS`): `judge-testina-placeholder`,
  `judge-samuel-seeddata`, `judge-fakename-example`
- run ids: `5eedda7a-0000-4000-8000-000000000001` (seeded published run,
  invalidated at the Sprint 6 publish swap),
  `5eedda7a-0000-4000-8000-000000000002` (unpublished decoy)

Deleting the invalidated seeded run deliberately surrenders it as a rollback
target (Sprint 7 SD 2): once 29.3 republishes, real runs are each other's
rollback targets under the published-run model.

## 0. Preconditions

- Run on the workstation, never CI (the tool refuses if `CI` or
  `GITHUB_ACTIONS` is set).
- Postgres container up: `docker ps` shows `pca-postgres-1`.
- `DATABASE_URL` sourced at the CLI boundary — never auto-loaded:

  ```sh
  cd <repo-root>
  set -a; source .env; set +a
  ```

  All commands below assume this shell.

## 1. Pre-sweep snapshot (read-only)

Capture the "before" leg of the verification — the active published run id
must be identical before and after (AC 4c). Output is pasted verbatim into
the completion report.

```sh
docker exec -i pca-postgres-1 psql "${DATABASE_URL/localhost:5433/localhost:5432}" <<'SQL'
SELECT id, status, published_at IS NOT NULL AS published,
       invalidated_at IS NOT NULL AS invalidated
FROM analytics.aggregate_runs ORDER BY created_at;
SELECT slug FROM ref.normalized_judges
WHERE slug IN ('judge-testina-placeholder','judge-samuel-seeddata','judge-fakename-example');
SQL
```

Expected: exactly one row with `published = t AND invalidated = f` (the
active run — record its id); the seeded run `…0001` present and invalidated;
the decoy `…0002` present, unpublished; three fake judge slugs.

## 2. Dry run

```sh
pnpm --filter @pca/db run sweep:seeds -- --database pca
```

The dry run executes the deletes inside a transaction and rolls back, so the
reported counts are exact. Review: only the two registry run ids and the
three registry slugs appear; the active published run id printed matches
step 1. Nothing is deleted.

## 3. Execute

```sh
pnpm --filter @pca/db run sweep:seeds -- --database pca --confirm
```

One transaction; any interlock violation aborts and rolls back everything.
Refusal messages mean STOP-and-report — do not retry or work around:

- `reference a fake seed judge` — a real-data row FKs a sweep target.
- `is the active published run` / `is a registry run` — publication state
  does not match the spec.
- `is present but not invalidated` — the seeded run is not the inert
  rollback target the spec expects.

## 4. Idempotency proof (AC 7)

Re-run the exact command from step 3. Expected: every count is 0 and the
report ends with `no-op: nothing to sweep (all registry rows already
absent)`. Paste verbatim.

## 5. Post-sweep verification (read-only, agent-run)

a. Fake judges gone from public judge search (query tokens from the
registry display names):

```sh
# API pointed at the live DB, read-only:
pnpm --filter @pca/api run dev   # in a separate shell
for q in Testina Placeholder Samuel Seeddata Fakename Example; do
  curl -s "http://localhost:3001/api/v1/public/judges/search?q=$q"
done
```

Expected: zero results for every query.

b. Demo charges still served:

```sh
curl -s "http://localhost:3001/api/v1/public/charges/search?q=theft"
```

Expected: `retail-theft` among results.

c. Active published run unchanged: re-run the step 1 snapshot. Expected:
the same single active run id as before; registry runs absent.

d. All four public result states still serve (exemplars chosen from live
data at execution time — no pinned slugs; the old unavailable-arm
fixtures were the fake judges themselves):

- charge-only success: `GET /api/v1/public/results/charge/<slug>` for a
  charge with rows in the active run;
- judge-specific success: `GET /api/v1/public/results/charge/<slug>/judge/<judge-slug>`
  for a pair with rows in the active run;
- judge-unavailable arm: same endpoint for a roster judge with no rows
  in the active run;
- sentencing-unavailable arm: a charge with outcome rows but no
  sentencing rows in the active run.

Select exemplars read-only, e.g.:

```sql
-- pairs with rows (judge-specific success):
SELECT c.slug, j.slug FROM analytics.judge_outcome_aggregates a
JOIN ref.normalized_charges c ON c.id = a.charge_id
JOIN ref.normalized_judges j ON j.id = a.judge_id
WHERE a.aggregate_run_id = '<active-run-id>' LIMIT 3;
-- a roster judge with no rows in the active run (judge-unavailable):
SELECT slug FROM ref.normalized_judges j WHERE NOT EXISTS (
  SELECT 1 FROM analytics.judge_outcome_aggregates a
  WHERE a.judge_id = j.id AND a.aggregate_run_id = '<active-run-id>') LIMIT 3;
-- charges with outcomes but no sentencing (sentencing-unavailable):
SELECT c.slug FROM ref.normalized_charges c
WHERE EXISTS (SELECT 1 FROM analytics.charge_outcome_aggregates a
  WHERE a.charge_id = c.id AND a.aggregate_run_id = '<active-run-id>')
AND NOT EXISTS (SELECT 1 FROM analytics.charge_sentencing_aggregates s
  WHERE s.charge_id = c.id AND s.aggregate_run_id = '<active-run-id>') LIMIT 3;
```

If any verification step would require a write to the live DB:
STOP-and-report.

## `db:seed` and the live database (SD-3 resolution)

`pnpm db:seed` is guarded: `db/scripts/seed-guard.ts` runs first and REFUSES
(exit 2) when the target database contains real corpus data
(`raw.source_documents` or `fact.fact_build_runs` nonempty). Without the
guard, seeding the post-sweep live DB would re-insert the three fake judges
(the reference transaction commits first) and then fail on the
active-published unique index — partially reintroducing the launch-blocking
defect. Fresh dev databases and the CI service databases are empty at seed
time and seed exactly as before. An unmigrated target is refused with a
run-migrations-first message. The seed scripts in `db/seeds/` are unchanged.
