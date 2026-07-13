# Collector Commands Reference

_Status: reference (established Task COL-4b). Every `pipeline collect` invocation form, every
flag, and what each one means. Update in the same task whenever a collector flag changes._

The collector fetches docket-sheet PDFs from the UJS portal into directories under
`~/court-data/` (never inside a repo). It refuses to run in CI, needs the optional Playwright
group installed (`uv sync --group collector`, `uv run playwright install chromium`), and enforces
every counsel condition in code — the locked values in the last section are not flags and cannot
be changed from the command line.

```
pipeline collect --mode {enumerate|search|refresh} [flags]
```

---

## The three modes

### `--mode enumerate` (default) — docket-number range probing

Walks consecutive MC docket numbers (`MC-51-CR-#######-YYYY`) and fetches each sheet by
DocketNumber search. Coverage is a true denominator: hits AND misses are logged. MC only.

```
pipeline collect --year 2025 --start-seq 1 --count 600 --max-minutes 60
```

### `--mode search` — Date-Filed window discovery

One advanced search per calendar day in the range; harvests the CP/MC criminal rows from the
results grid and fetches the `--court`-selected rows in-session. Writes one window-ledger entry
per fetched court per searched window (court-scoped ledgers, COL-3); completed windows are
skipped on rerun. Requires `--start-date` and `--end-date`.

```
pipeline collect --mode search --court both \
  --start-date 2025-06-01 --end-date 2025-06-30 --max-minutes 240
```

### `--mode refresh` — pending-docket refresh (COL-4b)

Re-fetches exactly the loaded corpus's non-terminal dockets (any docket with a held charge:
`disposition_raw IS NULL`), derived from the database at run time, so later dispositions enter
the corpus via supersession. Classifies every fetched sheet `unchanged`/`changed` against the
docket's loaded source hash. Writes **no** window-ledger and **no** miss-ledger entries. Requires
`--refresh-dir`, an **explicit** `--court`, and `DATABASE_URL` in the environment (read at the
run boundary, never logged). Operate it only via the
[Refresh Cycle Runbook](intake/refresh-runbook.md).

```
pipeline collect --mode refresh --court both \
  --refresh-dir ~/court-data/refresh-intake-<UTC-date>/ --max-minutes 240
```

---

## Flags by mode

### Shared (all modes)

| Flag                       | Meaning                                                                                                                                                                                | Default                         |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `--mode`                   | `enumerate`, `search`, or `refresh` (see above).                                                                                                                                       | `enumerate`                     |
| `--court`                  | Enumerate: `MC` only. Search: `MC`/`CP`/`both` — gates which harvested rows are FETCHED. Refresh: `MC`/`CP`/`both` filters the target list; **must be explicit** (no default applied). | `MC` (enumerate/search)         |
| `--max-minutes`            | Wall-clock stop in minutes. Hard-capped at the counsel-locked 240-minute ceiling regardless of value.                                                                                  | `60`                            |
| `--report-dir`             | Parent for per-run report dirs (`<run-id>/attempts.jsonl` + `run-report.json`). Must be outside any git tree.                                                                          | `~/court-data/collection-runs/` |
| `--headless`               | Run the browser headless. Default is headful — the proven configuration and the honest posture.                                                                                        | off (headful)                   |
| `--batch-size`             | Real portal requests per batch before the inter-batch cooldown. Operational parameter.                                                                                                 | `100`                           |
| `--batch-cooldown-seconds` | Cooldown between batches. Operational, with an enforced **60s floor** (may be raised, never lowered below it).                                                                         | `120`                           |

### Enumerate mode only

| Flag               | Meaning                                                                                                 | Default                  |
| ------------------ | ------------------------------------------------------------------------------------------------------- | ------------------------ |
| `--year`           | Filing year of the enumerated range.                                                                    | `2025`                   |
| `--start-seq`      | First docket sequence to enumerate (1-based).                                                           | `1`                      |
| `--count`          | How many consecutive sequences to enumerate (the time cap usually ends the run first).                  | `600`                    |
| `--intake-dir`     | Where collected PDFs land (`<docket>.pdf`); the already-present skip checks here. Outside any git tree. | `~/court-data/intake/`   |
| `--ledger-dir`     | Home of the persistent miss ledger (`miss-ledger-<court>-<year>.jsonl`).                                | `~/court-data/coverage/` |
| `--recheck-misses` | Ignore the miss ledger this run and re-attempt every number (confirmed misses are re-appended).         | off                      |

### Search mode only

| Flag                | Meaning                                                                                                       | Default                  |
| ------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------ |
| `--start-date`      | First calendar day to search (ISO `YYYY-MM-DD`, inclusive). Required.                                         | —                        |
| `--end-date`        | Last calendar day to search (ISO `YYYY-MM-DD`, inclusive). Required.                                          | —                        |
| `--intake-dir`      | As in enumerate mode: PDF landing zone + the already-present fetch skip.                                      | `~/court-data/intake/`   |
| `--ledger-dir`      | Home of the court-scoped window ledgers (rerun-skip of completed windows).                                    | `~/court-data/coverage/` |
| `--recheck-windows` | Ignore the window ledger and re-search every window in range (truncated/blocked windows always retry anyway). | off                      |

### Refresh mode only

| Flag            | Meaning                                                                                                                                                                                                                                                    | Default |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| `--refresh-dir` | **Required.** Cycle-scoped directory where re-fetched sheets land. One fresh dated dir per cycle; the SAME dir across that cycle's sessions (a PDF already present skips as `already_fetched`, making interrupted cycles resumable). Outside any git tree. | —       |

Refresh also requires `DATABASE_URL` in the environment (target-list derivation) and ignores
`--intake-dir`/`--ledger-dir` entirely: it never consults the intake dir (its fetch universe is
the derived target list — that is the scoped already-present bypass) and never writes any ledger.

### Search + refresh (smoke tooling)

| Flag            | Meaning                                                                                                            | Default |
| --------------- | ------------------------------------------------------------------------------------------------------------------ | ------- |
| `--max-fetches` | Cap on live PDF fetches for the whole run; reaching it stops the run (`fetch_cap`). Never used in production runs. | none    |

---

## Counsel-locked values (NOT flags — cannot be changed from any command line)

| Condition               | Value                                                                          | Source                                  |
| ----------------------- | ------------------------------------------------------------------------------ | --------------------------------------- |
| Session ceiling         | 240 minutes                                                                    | ADR 0002 (≤ 4h continuous per session)  |
| Post-block cooldown     | 300 seconds                                                                    | ADR 0002 amendment (≥ 2-minute minimum) |
| Per-request delay       | 2.0–5.0 s jittered, after EVERY portal request                                 | COL-1 FIX 1                             |
| Block streak stop       | 5 consecutive blocks                                                           | ADR 0002 / COL-1                        |
| Error streak stop       | 5 consecutive errors                                                           | COL-1 FIX 2                             |
| Daily cap (operational) | ≤ 8h collection per day, break between sessions — runbook discipline, not code | ADR 0002                                |

Every run writes `attempts.jsonl` (per-attempt good-faith record; docket numbers permitted) and
`run-report.json` (counts, statuses, parameters — no docket numbers) under
`<report-dir>/<run-id>/`. Console output is counts/statuses only.

## Related commands

| Command                          | What it does                                                                                                   |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `pipeline migrate-window-ledger` | One-time COL-3 migration: split the shared window ledger into court-scoped ledgers (offline).                  |
| `pipeline prune-fact-runs`       | Delete fact build runs whole so supersessions can proceed — the pre-refresh step; dry-run without `--confirm`. |
