# ADR 0004: Deployment — Stack, Data Path, Topology, Rate Limiting, Operations

Status: Accepted
Date: 2026-07-15

## Context

Phase 31 takes the project from a locally verified build to a small public
deployment. The 31.3 decision gate (held in planning chat, informed by the
31.3-R code recon) ruled on hosting, region, domain, the production data
path, API topology, rate limiting, probes, configuration guards, secrets
handling, and rollback. This ADR records those rulings and their rationale
so the go-live runbooks (`docs/runbook-go-live.md`,
`docs/runbook-verification.md`, `docs/runbook-rollback-republish.md`) can be
executed without re-litigating any decision. Prices referenced during the
gate are July 2026 readings and are re-verified at execution time.

## Decisions

### 1. Hosting stack

Render, with two Starter-tier services (web and API) and Render Postgres
Basic pinned to PostgreSQL 17. Cloudflare provides registrar, DNS, and
proxy. UptimeRobot (free tier) provides external probes. Free-tier compute
or database instances are prohibited for every component — idle spin-down
and autosuspend behaviors are incompatible with keyword probes and a public
service.

Rejected alternatives:

- Railway — the fixed-price plan that made it attractive was discontinued.
- Vercel Hobby — terms-of-service posture is a poor fit for a civic
  project of this kind.
- Neon free tier — autosuspend interacts badly with external probes.
- A general-purpose VPS — 2026 repricing removed the cost advantage.
- Supabase — pauses idle databases on the relevant tier.

### 2. Region

US-East class, and ALL Render resources in the same region — Render's
internal networking (which the private-API topology depends on) requires
same-region placement.

### 3. Domain

`philacourtoutcomes.org`, registered at Cloudflare Registrar (.org, at-cost
pricing, WHOIS redaction). Pre-approved fallback if the primary is taken at
registration time: `philadelphiacourtoutcomes.org`.

### 4. Production data path (Q3) — Option A, migrator-fresh variant

The production database is created empty (database name `pca`, user `pca` —
permanent and deliberate; PostgreSQL 17; US-East), the repo migrator is run
against it (`pnpm db:migrate:latest` with the production URL), and then a
data-only dump of EXACTLY the nine public tables is taken from the local
`pca` database and restored with `pg_restore --single-transaction`.

The nine tables (the compile-enforced public API surface,
`apps/api/src/db.ts`):

1. `ref.normalized_charges`
2. `ref.charge_aliases`
3. `ref.normalized_judges`
4. `ref.judge_aliases`
5. `analytics.aggregate_runs`
6. `analytics.charge_outcome_aggregates`
7. `analytics.charge_sentencing_aggregates`
8. `analytics.judge_outcome_aggregates`
9. `analytics.judge_sentencing_aggregates`

Republishing to production is a re-run of the same dump/restore procedure.
Migration bookkeeping tables (`public.kysely_migration`,
`public.kysely_migration_lock`) always come from running the migrator,
never from the dump.

`db:seed` against production is PROHIBITED. The seed path injects
fake-judge and synthetic-aggregate rows (the 29.1 defect class, proven in a
dry run); it exists for CI and local test databases only.

Option B (the pipeline publishing directly into a separate target database)
was rejected for launch: the 31.3-R recon showed the aggregates commands
read facts and write aggregates over a single connection resolved from one
`DATABASE_URL`, so a source/target split is a real development task, not a
configuration change. It sits in the post-launch queue.

### 5. API topology

The API is a Render PRIVATE service. The web service reaches it via the
internal hostname carried in `API_BASE_URL`. No public API hostname exists;
the only public surface is the web app (which proxies `/api/v1/public/*`
via its rewrite). `/health` is the Render internal health-check path — it
is DB-independent by construction and reports process liveness only.

### 6. Rate limiting — two layers

- Edge: Cloudflare's one free unmetered rate rule on `/api/*` at
  ~300 requests/minute per IP. This is the per-IP layer; it sees real
  client addresses. Applied operationally (runbook step).
- In-app: `@fastify/rate-limit` registered inside the public-routes
  encapsulation scope, emitting catalog-conformant `RATE_LIMITED` 429s
  through the existing central error handler, defaulting to
  120 requests/minute.

In-app keying is a CONSTANT key (one global bucket), not per-IP. The 31.3
recon established that no reliable client identity reaches the private API:
server-side fetches from the web app carry no client headers, the Next.js
rewrite proxy adds only `x-forwarded-host` (never `x-forwarded-for`), and
the API does not (and should not) trust forwarded headers from an
unverified chain. The in-app limiter is therefore a coarse global backstop
protecting the API and database; per-client fairness is the edge layer's
job. Thresholds are env-tunable (`RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW_MS`)
with the ruled defaults; there is no disable path and no environment
branch.

`/health` is structurally outside the limited scope (it is registered at
the application root, not under `/api/v1/public`), so health checks and
probes can never be throttled.

### 7. Probes

UptimeRobot, two monitors, both via the public domain:

1. HTTP monitor on the site root — web service up.
2. Keyword monitor on `/api/v1/public/data-coverage` expecting
   `"available":true` — proves the full path: web, rewrite/API, database,
   and an active published aggregate run. The endpoint's response is an
   HTTP-200 tagged union, so this keyword cleanly separates "serving a
   published run" from "up but nothing published" (`"available":false`)
   and from hard failure (non-200).

Cloudflare Bot Fight Mode stays OFF — it interferes with legitimate
monitoring and adds no needed protection at this scale.

### 8. API_BASE_URL production guard

`resolveApiBaseUrl` (apps/web/app/lib/api-base-url.ts) THROWS when
`NODE_ENV === 'production'` and `API_BASE_URL` is unset or empty. The
local-dev default (`http://localhost:3001`) is retained for `next dev` and
tests. Because next.config.ts resolves the base at config load, a
misconfigured production environment fails at `next build` / `next start` —
loudly, before serving traffic. This retires the launch-readiness item that
previously tracked the silent localhost fallback.

### 9. Secrets

Render per-service environment variables only.

- API service: `DATABASE_URL` (internal connection string),
  `HOST=0.0.0.0`, `NODE_ENV=production`.
- Web service: `API_BASE_URL` (internal API address) — present at BUILD
  time and at runtime.
- `DEFENDANT_HASH_SALT` exists NOWHERE in production: the aggregates
  commands do not read it, and the pipeline never runs on Render.

Production secrets never enter the repo and are never written to any file
on local disk. Entry patterns that keep values out of shell history are
mandatory (see the runbooks).

### 10. Rollback

- Code: Render per-service rollback to the previous deploy.
- Data: production is a disposable mirror. Canonical truth is the local
  `pca` database plus the local court-data artifacts; recovery is a
  re-run of the nine-table dump/restore.
- Edge: Cloudflare can hold traffic or point the domain away.

### 11. noindex verification (live)

The app serves an unconditional noindex; verification (not assumption)
covers all three hostname surfaces: the domain root, one result page, and
the web service's `*.onrender.com` hostname. Header/meta assertions on each.

### 12. Run-report file emission

DEFERRED to the post-launch queue (named at 31.4). The standing rule —
acceptance-relevant console output is captured verbatim, by copy-paste,
never retyped — remains in force for all go-live operations.

### 13. Sequencing

This task's commit → phase-31 PR → CI green → merge → runbooks executed
against merged main → 31.4 → close-out branch (README live-URL line +
ops/close worklog) → second PR. Deployment builds only ever come from
`main`.

## Hazards (recorded deliberately)

1. `CI` / `GITHUB_ACTIONS` environment variables brick pipeline publish:
   the aggregates commands refuse to run when either is set
   (services/pipeline/src/pipeline/cli.py). Never set them on any host that
   runs pipeline commands.
2. The API start script uses `--env-file-if-exists=../../.env`
   (apps/api/package.json). A stray `.env` bundled into a deploy image
   would silently take precedence over injected environment variables.
   Deploy images must not contain `.env` files.
3. The API's `HOST` default is `127.0.0.1` (apps/api/src/env.ts) —
   loopback-only, container-breaking. Production must set `HOST=0.0.0.0`
   explicitly.
4. The silent localhost fallback in `API_BASE_URL` resolution is closed by
   this task's guard (Decision 8); before it, an unset production value
   quietly pointed the web app at localhost.
5. The in-app rate-limit bucket is per-instance and in-memory: horizontal
   scaling multiplies the effective global limit by the instance count.
   The edge per-IP rule is unaffected. Launch runs a single Starter
   instance; any future scale-out must revisit the backstop so it does not
   silently loosen.
6. Prices cited at the gate are July 2026 readings; re-verify at execution.

## Addendum — go-live execution rulings (2026-07-16)

Recorded at Sprint 7 close-out. This addendum completes 31.3
implementation AC 8 (the ADR captures the decisions actually executed).
Each ruling below was adjudicated in the planning chat during go-live
execution; rationale is recorded so future readers re-litigate nothing.

1. **Database storage: 1 GB initial, Storage Autoscaling OFF** (amends
   Decision 1's Postgres line). The production database is a tiny
   public-table mirror of nine aggregate/reference tables; storage sizing
   is one-way (it grows but never shrinks back), and autoscaling would be
   silent cost drift with no corresponding need.

2. **TLS: `verify-full` end-to-end on BOTH client stacks; `sslmode=require`
   is BANNED.** The Node migration runner opts in via
   `?sslmode=verify-full` appended to the connection URL; every
   prod-touching libpq tool (`psql`, `pg_restore`) takes a per-command
   `PGSSLMODE=verify-full PGSSLROOTCERT=system` prefix, never exported.
   `sslmode=require` is banned because the pinned driver emits a security
   warning for it and its semantics change in pg v9 (adjudicated at 31.3c;
   a lock test pins the behavior).

3. **Cloudflare encryption mode: Full BEFORE any DNS records; Full
   (strict) is the verified end state**, reached via the post-deploy
   one-shot once the Render origin certificate exists. Full-first closes
   the window where a default/Flexible mode could serve during DNS
   cutover; strict-first is impossible (no origin certificate yet); Full
   (strict) is the only end state that authenticates the origin.

4. **Edge rate rule: 50 requests / 10 seconds per IP, action Block,
   minimum (10 s) mitigation timeout.** This is Decision 6's
   ~300 requests/minute/IP expressed under the free plan's fixed
   10-second counting window — average-identical, tighter on bursts,
   accepted as such. Future readers correct it in neither direction. Bot
   Fight Mode confirmed OFF (Decision 7 unchanged).

5. **Health check (amends Decision 5):** the API is a Render PRIVATE
   service, and private services take the platform-default TCP probe —
   no health-check path can be configured, so Decision 5's "`/health` is
   the Render internal health-check path" is retired as written.
   `/health` remains DB-independent process liveness and is verified
   post-deploy: directly via the API service Shell and transitively via
   the keyword monitor. Deploy-green claims are stated under TCP
   semantics only.

6. **Domain: `philacourtoutcomes.org` registered** — the pinned primary;
   the pre-approved fallback was not needed. Registration actual: $8.50
   at-cost (Decision 3 executed as ruled).

7. **Cost actuals (execution-time readings, per the re-verify rule):**
   API service $7/mo (Starter), web service $7/mo (Starter), Render
   Postgres Basic $6/mo, domain $8.50/yr at-cost.

8. **UptimeRobot free-tier terms note:** secondary sources describe the
   free tier as personal/non-commercial use since October 2024; this
   project is non-revenue civic transparency. A primary-source read of
   the ToS is queued in the post-launch queue; the two monitors stand as
   deployed (Decision 7) pending that read.
