# PCA Handoff — 2026-07-25

For the next planning chat. Read this plus `docs/board.md` in the repo — the board is the source of truth for current state; this file carries the live thread and the new way of working.

---

## How we work now (changed 2026-07-25 — this supersedes the old process)

The heavy process (formal specs, adjudication gates, relay files, plan-approval ceremony) is **retired**. It existed for a blind planner and a deadline; neither applies anymore. Chops is a solo builder with no time limit.

- **Cowork** = planning/analysis brain. Reads the repo and `~/court-data`. Talk to it in plain words.
- **Claude Code** = hands. Code, tests, migrations, pipeline runs, DB queries. Talk to it in plain words.
- **This chat (claude.ai)** = optional thinking partner. It cannot see the disk — never treat its recall as truth; the board is truth.
- **`docs/board.md`** = the state file. Any session opens by reading it; update it when things change. This is the one habit that matters.

The rules that still bind (these are real, everything else is optional):

1. Nothing derived from real dockets ever enters the repo tree.
2. Don't break the live site — eyeball diffs before anything that re-parses the corpus or republishes.
3. Copy stays honest — no predictions, no rankings, no judge/attorney comparisons without a deliberate ruling.
4. Tests green before deploy. A before/after number on any data-changing fix.

## Where the project is

- Live: philacourtoutcomes.org, run `9b870800`, 37,369 dockets. Site is healthy; nothing on fire.
- Demo day done (runner-up). No deadline. Focus: fix internals before building roadmap features.
- Chops is running a background refresh pass (right-censoring recovery); arrivals sit in the refresh dir and load at the next intake cycle.
- The 36.0 / 36.0-A recon program is COMPLETE. Findings on disk: `~/court-data/recon-36.0-A/` (outputs + triage) and `~/court-data/reports/recon-36.0-20260724T235427Z.md`.

## What the recon found (the fix list, in Chops's order)

1. **Invisible charges — IN FLIGHT, decision made.** ~6,033 disposed in-window charges match no roster entry. Triage of the top 50 forms: **33 new charges + 2 aliases + 1 junk (skip)**. Decision: [CHOPS FILLS IN: all 33 + 2 aliases? traffic offenses in or out? the 2 thin ones?]. The build: seed rows in `ref.normalized_charges` / `ref.charge_aliases`, tests, matcher rerun, **before/after matched-count as proof** (~3,200 expected recovered from the top 50). Watch the 75 § 3802 asterisk hazard on the DUI alias (`charge_matcher.py:98-107`). Triage table: `~/court-data/recon-36.0-A/` outputs.
2. **Review queue (~1k open, ~882 blocking otherwise-eligible facts).** A triage session: group by type, close the junk, fix what's real. Worth up to ~882 public facts.
3. **404 bug.** Unknown charge slugs serve HTTP 200 in dev AND prod (streaming boundary — route-level `loading.tsx` flushes before `notFound()` sets status); judge route soft-404s by design. One fix, small. Must land before search-engine indexing is ever enabled.
4. **Then build:** funnel numbers on charge pages + analytics page + the noindex (indexing) decision.
5. **Later:** attorney/prosecutor stats (needs recon: do sheets carry counsel names?), richer charts.

## One design landmine, already defused (note for the funnel build, item 4)

MC→CP double-counting is real: up to ~27,828 held charges (66% of the held bucket) reappear on their CP successor docket — retail theft: 534 of 598. Nothing live today is wrong (outcomes aren't doubled), but a naive "charges seen" funnel count would be inflated on every page. The linkage to handle it exists (`parsed.docket_links`, docket-grain, 87% resolved, 97.4% charge-concordant). Leaning: disclose-don't-infer (show the overlap as a number, wedge-style) — decide when the funnel gets built, not before.

## Small loose ends (whenever)

- `docs/board.md` and `docs/process-rulings.md` are untracked — commit them.
- After the roster fix lands: one rebuild → publish cycle picks up the roster fix AND the refresh arrivals together (one cycle, not two).
- The 33 ambiguous disposed rows are all one defect shape (statute/text conflict, mostly Harassment/Trespass variants) — a handful of roster corrections clears them; can ride the roster task.

## What the next chat should do first

Ask Chops where the roster task stands (dispatched? done?), read the board, and help with whatever's next on the list above — in plain words, no ceremony.
