# Runbook: Go-Live (Phase 31)

Executes the ADR 0004 decisions in order. Every step ends with a
verification checkpoint — do not proceed past a failed checkpoint. All
acceptance-relevant console output is captured VERBATIM (copy-paste, never
retyped) to `~/court-data/reports/` per the standing rule.

Secret hygiene (applies to every step):

- The production `DATABASE_URL` is never written to any file, never echoed,
  never pasted into a command line directly (command lines enter shell
  history). Enter it via `read -s` into an environment variable:

  ```sh
  read -s PROD_DATABASE_URL   # paste the value, press enter; nothing echoes
  export PROD_DATABASE_URL
  ```

  When finished with a session: `unset PROD_DATABASE_URL`.

- All other secrets live only as Render per-service environment variables.

Prerequisites:

- Phase-31 PR merged; deployment builds come from `main` only.
- PostgreSQL 17 client tools locally. This is a GATE, not a sentence — run
  all three, each must report 17.x (the client pair must match the server
  major); do not proceed past a mismatch:

  ```sh
  psql --version         # expected: psql (PostgreSQL) 17.x
  pg_dump --version      # expected: pg_dump (PostgreSQL) 17.x
  pg_restore --version   # expected: pg_restore (PostgreSQL) 17.x
  ```

- Prices quoted in ADR 0004 are July 2026 readings — re-verify each on the
  provider's pricing page before creating the resource, and record actuals.

Hazard reminders (ADR 0004 Hazards):

- Never set `CI` or `GITHUB_ACTIONS` on any host that runs pipeline commands.
- Deploy images must not contain `.env` files (the API start script would
  silently prefer one).
- The API needs explicit `HOST=0.0.0.0`; its default is loopback-only.

---

## Step 1 — Domain registration (Cloudflare)

1. In Cloudflare Registrar, register `philacourtoutcomes.org` (.org,
   at-cost, WHOIS redaction on).
2. If it is unavailable at registration time, register the pre-approved
   fallback `philadelphiacourtoutcomes.org` instead and use it everywhere a
   domain appears below.

**Checkpoint:** the domain appears in the Cloudflare dashboard as active,
using Cloudflare nameservers, WHOIS redaction enabled.

## Step 2 — Production database (Render)

1. Create a Render Postgres instance: plan **Basic** (not free),
   PostgreSQL version **17**, region **US-East class** (record the exact
   region — every later resource must use the same one), database name
   `pca`, user `pca` (permanent, deliberate), initial storage **1 GB**,
   Storage Autoscaling **off** (ruled: this is a tiny public-table mirror;
   storage sizing is one-way, and autoscaling would be silent cost drift).
2. Record the INTERNAL connection string (for the API service) and the
   EXTERNAL connection string (for the migrate/restore steps below). Do not
   write either to a file.

**Checkpoint:** instance status is Available; the dashboard shows PG 17,
the chosen region, database `pca`, user `pca`, storage 1 GB, Storage
Autoscaling off.

## Step 3 — Migrate the production database

Render external endpoints REQUIRE TLS: a plain connection is refused at
handshake time with `SSL/TLS required` before any migration runs. The
Node migration runner (`pg`) does not attempt TLS unless the connection
string opts in, so the invocation below appends `?sslmode=verify-full` —
TLS with full certificate-chain and hostname verification against the
system CA store (Render's external chain is publicly trusted; verified
2026-07-15, probe evidence in `~/court-data/reports/`). Do NOT use
`sslmode=require`: in the pinned driver it emits a security warning and
its semantics change in pg v9.

The `?` joiner presumes the pasted external URL carries no existing
query string (Render's currently does not). If it ever does, join with
`&` instead of `?`.

From the repo root on `main` (fresh `git pull`; `pnpm install` current):

```sh
read -s PROD_DATABASE_URL    # external connection string from Step 2
export PROD_DATABASE_URL
DATABASE_URL="${PROD_DATABASE_URL}?sslmode=verify-full" pnpm db:migrate:latest
```

**Checkpoint:** the migrator reports every migration in `db/migrations/`
applied and exits 0. Confirm bookkeeping came from the migrator (SELECT-only):

```sh
PGSSLMODE=verify-full PGSSLROOTCERT=system \
  psql "$PROD_DATABASE_URL" -c 'select count(*) from public.kysely_migration;'
```

TLS note for `psql` (and every libpq tool below): libpq defaults to
`sslmode=prefer` — encrypted but with an UNVERIFIED certificate chain.
The inline `PGSSLMODE=verify-full PGSSLROOTCERT=system` prefix enforces
verified TLS; `sslrootcert=system` (PG ≥ 16 client) points libpq at the
system trust store. Keep the prefix per-command, never `export`ed — and
never put `sslrootcert=system` in a URL the Node driver sees (node-pg
would read it as a file path named `system` and crash).

The count equals the number of files in `db/migrations/` at run time.

## Step 4 — Nine-table dump/restore (Q3 Option A, migrator-fresh)

`db:seed` against production is PROHIBITED (ADR 0004 Decision 4). The only
data path is this dump/restore. The dump format and restore tool are a
matched pair: **custom-format `pg_dump -Fc`** read by **`pg_restore`**.

1. Dump exactly the nine public tables from the local `pca` database
   (data-only, custom format). The local URL is the non-secret local-dev
   one from the repo-root `.env`. TLS: none — this reads the LOCAL docker
   Postgres, which does not speak TLS; no SSL settings apply here:

   ```sh
   set -a; . ./.env; set +a   # loads local DATABASE_URL (local dev values)
   pg_dump -Fc --data-only \
     -t ref.normalized_charges \
     -t ref.charge_aliases \
     -t ref.normalized_judges \
     -t ref.judge_aliases \
     -t analytics.aggregate_runs \
     -t analytics.charge_outcome_aggregates \
     -t analytics.charge_sentencing_aggregates \
     -t analytics.judge_outcome_aggregates \
     -t analytics.judge_sentencing_aggregates \
     -f /tmp/pca-public-9table.dump \
     "$DATABASE_URL"
   ```

2. Build an explicitly FK-ordered restore list. A data-only restore does
   not reorder for foreign keys on its own, so the order is pinned here:
   parents before children (all twelve FK edges among the nine tables point
   from aliases/aggregates to `normalized_charges`, `normalized_judges`,
   and `aggregate_runs`):

   ```sh
   pg_restore -l /tmp/pca-public-9table.dump > /tmp/toc.full
   : > /tmp/toc.ordered
   for t in normalized_charges normalized_judges aggregate_runs \
            charge_aliases judge_aliases \
            charge_outcome_aggregates charge_sentencing_aggregates \
            judge_outcome_aggregates judge_sentencing_aggregates; do
     grep "TABLE DATA .* $t " /tmp/toc.full >> /tmp/toc.ordered
   done
   wc -l /tmp/toc.ordered   # must print 9
   ```

3. Restore into production in a single transaction (any failure — including
   a foreign-key violation — rolls back everything). TLS: `pg_restore` is a
   libpq tool — the inline prefix enforces verified TLS exactly as in the
   Step 3 checkpoint note:

   ```sh
   PGSSLMODE=verify-full PGSSLROOTCERT=system \
     pg_restore --single-transaction --data-only \
     -L /tmp/toc.ordered \
     -d "$PROD_DATABASE_URL" \
     /tmp/pca-public-9table.dump
   ```

4. Delete the dump artifacts: `rm /tmp/pca-public-9table.dump /tmp/toc.full /tmp/toc.ordered`
   (aggregate-only data, but production posture is no lingering copies).

**Checkpoint (two parts, both SELECT-only):**

- `pg_restore` exited 0. Because the restore ran `--single-transaction`
  with a pinned FK-safe order, a zero exit IS the proof that restore
  ordering satisfied every foreign key.
- Per-table count comparison against the local source AT RUN TIME (no
  pinned counts). Run the same query against both URLs and compare the two
  outputs line by line — they must be identical. TLS differs per target, so
  the two invocations are explicit rather than a loop: the local docker
  Postgres speaks no TLS (a `verify-full` prefix there would fail the
  connection), while the production psql run takes the verified-TLS prefix
  from the Step 3 checkpoint note:

  ```sh
  COUNT_SQL="
    select 'ref.normalized_charges', count(*) from ref.normalized_charges
    union all select 'ref.charge_aliases', count(*) from ref.charge_aliases
    union all select 'ref.normalized_judges', count(*) from ref.normalized_judges
    union all select 'ref.judge_aliases', count(*) from ref.judge_aliases
    union all select 'analytics.aggregate_runs', count(*) from analytics.aggregate_runs
    union all select 'analytics.charge_outcome_aggregates', count(*) from analytics.charge_outcome_aggregates
    union all select 'analytics.charge_sentencing_aggregates', count(*) from analytics.charge_sentencing_aggregates
    union all select 'analytics.judge_outcome_aggregates', count(*) from analytics.judge_outcome_aggregates
    union all select 'analytics.judge_sentencing_aggregates', count(*) from analytics.judge_sentencing_aggregates;"
  psql "$DATABASE_URL" -At -c "$COUNT_SQL"          # local: docker, non-TLS
  PGSSLMODE=verify-full PGSSLROOTCERT=system \
    psql "$PROD_DATABASE_URL" -At -c "$COUNT_SQL"   # production: verified TLS
  ```

## Step 5 — API service (Render, PRIVATE)

1. Create a **Private Service** from the repo (branch `main`), plan
   **Starter**, same region as the database.
2. Build command (the CI-proven path; `pnpm generate` MUST precede builds —
   taxonomy artifacts are gitignored):

   ```sh
   pnpm install --frozen-lockfile && pnpm generate && pnpm run build:packages && pnpm --filter @pca/api run build
   ```

3. Start command:

   ```sh
   pnpm --filter @pca/api run start
   ```

4. Environment variables (per-service, ADR 0004 Decision 9):
   - `DATABASE_URL` = the INTERNAL connection string from Step 2
   - `HOST` = `0.0.0.0` (mandatory — the default is loopback-only)
   - `NODE_ENV` = `production`
   - Do NOT set `PORT` manually if Render injects it; the API reads `PORT`
     with a 3001 fallback. Record the port the service actually listens on.
   - Do NOT set `CI` or `GITHUB_ACTIONS`. `DEFENDANT_HASH_SALT` must not
     exist on this service.
5. Health check: configure NOTHING. Render private services take the
   platform-default TCP probe; the health-check path field does not exist
   on them. Deploy-green therefore means TCP semantics only — build
   succeeded, process started, port accepting connections — and carries NO
   `/health` claim. `/health` verification lives in
   `docs/runbook-verification.md`: direct via the API service Shell, and
   transitive via the Step 9 keyword monitor.

**Checkpoint:** deploy succeeds (TCP semantics only, per above); record the
internal address VERBATIM (`<internal-host>:<port>`) — it becomes the web
service's `API_BASE_URL` value (`http://<internal-host>:<port>`) in Step 6.

## Step 6 — Web service (Render)

1. Create a **Web Service** from the repo (branch `main`), plan **Starter**,
   same region.
2. Set the environment variable BEFORE the first build (it is read at build
   time by `next build` and the guard throws without it):
   - `API_BASE_URL` = `http://<api-internal-host>:<port>` from Step 5.
3. Build command:

   ```sh
   pnpm install --frozen-lockfile && pnpm generate && pnpm run build:packages && pnpm --filter @pca/web run build
   ```

4. Start command:

   ```sh
   pnpm --filter @pca/web run start
   ```

   (`next start` binds Render's injected `PORT`.)

**Checkpoint:** deploy succeeds; the `*.onrender.com` URL serves the
homepage AND one charge result page renders with data (server-side fetch →
internal API → database → published run, end to end).

## Step 7 — DNS, TLS mode, and proxy (Cloudflare)

Sequencing is adjudicated and ordered — do not reorder:

1. BEFORE creating any DNS records: set the zone's SSL/TLS encryption mode
   to **Full**. **Full (strict) is the verified end state**, reached via
   the post-deploy one-shot in item 6 — never Flexible, and never
   strict-first (the Render origin certificate does not exist yet).
2. Add the domain (apex and `www`) as custom domains on the Render web
   service.
3. In Cloudflare DNS, create BOTH records — `@` (apex; Cloudflare flattens
   CNAME at the apex) and `www` — as CNAMEs to the web service's ACTUAL
   `*.onrender.com` hostname recorded in Step 6, **DNS only (grey cloud)**,
   not proxied. AAAA / fresh-zone note: a fresh zone starts empty, so there
   are no stale AAAA (or other) records to collide with; if the zone is NOT
   fresh, audit and remove stale records for these names first.
4. Wait for Render's domain verification to complete AND its certificate
   to issue.
5. Only then flip BOTH records to **Proxied** (orange cloud).
6. Post-deploy one-shot (after the proxied names serve): flip the zone's
   encryption mode Full → **Full (strict)** and re-verify both names in one
   shot — `curl -sI https://<domain>/` and `https://www.<domain>/` return
   200 with `www` redirecting to the apex, and `openssl s_client` against
   each shows `Verify return code: 0 (ok)`.

The Step 3 `?`-joiner assumption on the URL parameter is retained
unchanged (see Step 3); nothing in this step alters it.

**Checkpoint:** `https://<domain>/` loads the homepage with a valid
certificate; `https://www.<domain>/` resolves and redirects to the apex; a
result page loads over the domain; encryption mode reads **Full (strict)**
after the item-6 one-shot.

## Step 8 — Edge rate rule + Bot Fight Mode

1. Create the one free unmetered Cloudflare rate limiting rule: expression
   "URI Path starts with `/api/`", threshold **50 requests / 10 seconds
   per IP**, action **Block**, mitigation timeout at the form's minimum
   (expected 10 seconds).

   Derivation note: 50/10s is the ~300 requests/minute/IP decision
   (ADR 0004 Decision 6) expressed under the plan's FIXED 10-second
   counting window — average-identical, tighter on bursts. Future readers
   correct it in NEITHER direction: do not "fix" the rule up to 300/min,
   and do not "fix" the ADR down to 50/10s-as-a-new-decision.

2. Bot Fight Mode is OFF — verify the toggle (it interferes with
   legitimate monitors and adds no needed protection at this scale).

**Checkpoint:** the rule shows Active on the `/api/` path expression at
50 requests / 10 seconds per IP, action Block, minimum mitigation timeout;
Bot Fight Mode toggle shows Off.

## Step 9 — UptimeRobot monitors

1. HTTP monitor: `https://<domain>/` (web up).
2. Keyword monitor: `https://<domain>/api/v1/public/data-coverage`,
   keyword `"available":true`, alert when missing. This proves
   web → rewrite → API → database → active published run through the real
   path. (Monitor interval 5 minutes: negligible against the in-app
   120/min bucket; it can never hit `/health`, which is not throttled
   anyway — see ADR 0004 Decision 6.)

**Checkpoint:** both monitors report Up/keyword-found after their first poll.

## Step 10 — noindex verification (three surfaces)

The app serves an unconditional noindex; verify it on every hostname
surface (verified, never assumed):

```sh
for u in "https://<domain>/" \
         "https://<domain>/charges/<any-live-slug>" \
         "https://<web-service>.onrender.com/"; do
  echo "== $u"
  curl -sI "$u" | grep -i 'x-robots-tag' || true
  curl -s  "$u" | grep -io '<meta[^>]*robots[^>]*>' || true
done
```

**Checkpoint:** every surface shows noindex via header and/or meta tag;
paste the output verbatim. If any surface lacks it, STOP — do not announce
the URL — and report.

## Step 11 — Hand off

Proceed to `docs/runbook-verification.md` (post-deploy verification: agent
read-only checks, then the demo-script smoke).
