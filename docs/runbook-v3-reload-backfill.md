# Runbook — record-v3 reload + charge-supersession backfill (Phase 36)

**What this cycle does.** Record parser v3 captures two fields that were
always in the extracted text and previously discarded: the CP sheet's
`Originating Docket No` (case grain) and the charge table's `Orig Seq`
column (charge grain). A reload from the stored envelopes populates them;
the backfill then derives `parsed.charges.superseded_by_charge_id` — the
MC→CP double-count fix — from the deterministic join:

    case level:   CP.originating_docket_no = MC.docket_number AND OTN match
    charge level: CP.orig_seq = MC.sequence AND statute match
    guard:        the MC charge's CURRENT disposition is a held form
    multi-claim:  the latest-filed CP case wins (remand/refile second rounds)

No re-downloading and no re-extraction: the envelope parser stays at v8; the
version pair moves (8,2) → (8,3), so the loader takes the
`replaced_newer_version` arm per docket, exactly like the v7/v8 reload
cycles. Every fact build re-derives the supersession mapping from then on;
the standalone backfill exists so the pointers land without waiting for a
build.

**Expected diff shape (the rule-2 eyeball before anything runs):** the v2→v3
delta is NEW-FIELDS-ONLY by construction. The tier-1 goldens moved on exactly
three lines per record (`parser_version` 2→3, `case.originating_docket_no`,
`charges[].orig_seq`) and nothing else. If a tier-2 drift console shows any
diff outside those three field paths, STOP — that is a real parser change and
this runbook is stale.

## Order of operations

1. **Migrate.** `pnpm db:migrate:latest` against local canonical `pca`
   (adds `parsed.dockets.originating_docket_no`, `parsed.charges.orig_seq`,
   `parsed.charges.superseded_by_charge_id`, and
   `analytics.charge_volume_aggregates`). Non-destructive; instant.

2. **Reload from stored envelopes** — the standing full-corpus reload flow
   (the v8reload precedent): re-parse the stored envelope text with record
   v3 and `pipeline load` the outputs; the version tuple takes the
   newer-version arm per docket. Refresh tier-2 goldens with
   `--update-goldens` AFTER eyeballing that the drift is the three new-field
   paths only.

3. **Backfill.** `pipeline backfill-charge-supersession` (DATABASE_URL from
   the root `.env`; CI-guarded like every local command). It derives, writes
   the pointers in one transaction, prints the derivation counts, the top
   slugs by folded volume, and the pinned sanity line:

       retail-theft sanity line: seen=… outcomes=… held_untraced=… …

   **Sanity target (from the 36.0-A instruments): retail-theft lands near
   1,989 seen with ~534 folded into CP twins.** Large deviation = STOP and
   compare the derivation counts (`no_case_match` / `no_seq_match` /
   `statute_mismatch`) before touching anything else.

4. **Rebuild + regenerate at your cadence.** `pipeline build-facts` (now also
   re-derives supersession every run) → `pipeline generate-aggregates` (now
   also writes the volume population) → `pipeline validate-aggregates` (now
   also asserts volume closure, funnel-vs-percentages, and the fact-side
   sum; any violation blocks publish) → `pipeline publish-aggregates`.
   Outcome facts and every served percentage are unchanged by construction —
   only the volume/seen numbers are new.

5. **Republish to prod** per `docs/runbook-rollback-republish.md` — the
   restore surface is FIFTEEN tables now (`charge_volume_aggregates` joined
   the public set); both runbooks already carry it.

## The untraced remainder

Held charges whose CP case is not in the corpus stay counted as held for
court — time lag (CP case not filed yet) plus collection gap (CP case not
downloaded yet). The collection-gap fetch list is already in the links
table:

    SELECT DISTINCT target_docket_number
    FROM parsed.docket_links
    WHERE target_docket_id IS NULL;

Feeding those docket numbers to the collector and re-running the cycle
shrinks untraced to the true time-lag residue. A shrinking untraced count
across refreshes is the system working, not a defect.

## Ops dashboard

`ADMIN_OPS_ENABLED=1` on the local API turns on `/admin` in the web app —
every number (corpus, dedupe coverage, queue, builds, runs, outcomes, the
identity checks), polling live. The `cpDocketsWithOriginating` and
`chargesWithOrigSeq` tiles are the v3 reload's live progress meters; the
`supersededPointers` tile is the backfill's.
