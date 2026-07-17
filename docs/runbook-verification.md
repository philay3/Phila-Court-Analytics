# Runbook: Post-Deploy Verification (Phase 31)

Runs after `docs/runbook-go-live.md` completes. Two halves with a hard
boundary: the AGENT half is strictly read-only (GET requests and local
scratch scripts only — no repo writes, no committed tooling, no state
changes anywhere); the CHOPS half is the human walkthrough. Output capture
rule as always: acceptance-relevant console output is copy-pasted verbatim
to `~/court-data/reports/`.

---

## AGENT half (read-only)

### A1 — Endpoint availability sweep

Over the public domain (never the internal hostname — the point is the real
path), GET each endpoint and record status + a body excerpt:

- `/api/v1/public/data-coverage` — expect 200 with `"available":true`
- `/api/v1/public/definitions` — expect 200
- `/api/v1/public/methodology` — expect 200
- `/api/v1/public/charges/search?q=theft` — expect 200 with results
- `/api/v1/public/judges/search?q=a` — expect 200
- One `/api/v1/public/results/charge/<slug>` — expect 200
- One `/api/v1/public/results/charge/<slug>/judge/<slug>` — expect 200 or
  the documented 200-unavailable arm

Slugs come from the live search responses at run time — never from CI seed
data, which does not exist in production.

**Checkpoint:** every expected status matches; the data-coverage body says
`"available":true` with plausible run-time counts.

### A2 — noindex on all three hostname surfaces

Repeat the go-live Step 10 assertions (domain root, one result page, the
`*.onrender.com` hostname) and paste the output verbatim.

**Checkpoint:** noindex present on all three.

### A3 — Forbidden-field spot checks (one-off scratch invocation)

31.1-style scratch script, nothing committed: fetch each endpoint body from
A1 and run it through `scanForForbidden` from `@pca/shared/forbidden-scan`
(built dist). The endpoint list is A1's list — it mirrors the probe
registry that the committed privacy gates use
(`apps/api/src/test-support/public-route-probes.ts`), minus CI-seeded arms.

**Checkpoint:** zero violations on every body; paste the scan summary
verbatim.

### A4 — One controlled burst: live 429 at the edge (then stop)

Purpose: confirm the EDGE rate-limit layer fires in production. One burst,
once, then stop — do not repeat, do not script retries.

```sh
for i in $(seq 1 125); do
  curl -s -o /dev/null -w '%{http_code}\n' \
    "https://<domain>/api/v1/public/definitions"
done | sort | uniq -c
curl -s "https://<domain>/api/v1/public/definitions" | head -c 400; echo
```

Expected (32.4 A4 ruling — layer ordering is burst-speed-dependent): a
fast burst (>~5 req/sec) trips the Cloudflare edge rule FIRST — HTTP 429
with Cloudflare body `error code: 1015` at approximately 50 requests
inside a 10-second fixed window (the rule is 50 requests / 10 seconds per
IP; boundary and activation slop of a few requests is normal, and prior
requests in the same window shift the trip point). The in-app 120/min
catalog-shaped 429 (`RATE_LIMITED`, five fields) is exercised only by a
sustained ~2–5 req/sec probe and is authoritatively covered by the CI
inject tests; prod A4 verifies the EDGE layer only.

**Checkpoint:** 429s observed with the Cloudflare `1015` body at
approximately the 50-in-10s mark; paste the uniq count table and the body
verbatim. STOP after this — the window clears within seconds.

### A5 — Report

Assemble A1–A4 verbatim outputs into the run report under
`~/court-data/reports/` and post the summary in planning chat.

---

## CHOPS half

### C0 — API `/health` (direct via service Shell + transitive)

**Shell-guard rider (mandatory before ANY service-Shell check, here and
everywhere):** in the Render Shell, first assert the console identity —

```sh
printenv RENDER_SERVICE_NAME   # must print the intended service's name
```

— and proceed only if it names the service the check targets. Motivating
incident: during this runbook's item-4 `/health` check at go-live, the curl
was first run in the WRONG service's Shell (the web service, which listens
on the same port), returning the web app's 404 page — plausible-looking
evidence from the wrong console. Evidence must never come from an
unasserted shell.

1. Direct: in the API service's Shell, after the guard passes:

   ```sh
   curl -s "http://localhost:${PORT}/health"
   ```

   Expected body: `{"status":"ok",...}`. This is the only direct path —
   the API is private and has no public hostname.

2. Transitive: the UptimeRobot keyword monitor on
   `/api/v1/public/data-coverage` reports Up with the keyword found —
   web → rewrite → API → database through the real path (confirmed
   properly in C2).

**Checkpoint:** the direct body shows `"status":"ok"`; the keyword monitor
is Up.

### C1 — Demo-script smoke

Execute `docs/demo-script.md` end to end against the live domain (plan
AC 5): the twelve-step path, including the staleness re-verify walkthrough.
Any step that fails or renders unexpected copy is a STOP-and-report, not a
workaround.

**Checkpoint:** demo script completes; deviations (if any) recorded
verbatim in the run report.

### C2 — Monitor confirmation

After at least one UptimeRobot polling cycle: both monitors green; the
keyword monitor's last check shows the keyword found.

**Checkpoint:** screenshots or status output captured to the run report.
