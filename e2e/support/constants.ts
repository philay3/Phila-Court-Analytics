/**
 * Shared E2E constants (task 15.2; static since task STATIC-2b): the served
 * export's port and the seed slugs each flow exercises. Slugs are read off
 * db/seeds/reference-data.ts and db/seeds/aggregate-data.ts — the deterministic
 * seed set — never invented here. Any pinned user-facing COPY is imported from
 * @pca/shared (or the web copy modules) in the spec files, never re-typed.
 */

// The suite runs against the static export served with Cloudflare Pages
// semantics by `wrangler pages dev` (STATIC-2b pin 14). The port is
// configurable so a held 3000 is never a blocker: E2E_WEB_PORT=8788 pnpm test:e2e.
export const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 3000);
export const WEB_BASE_URL = `http://127.0.0.1:${WEB_PORT}`;

/**
 * Seed-slug fixtures, each mapped to the scenario it exercises. Sourced from
 * the deterministic seed files:
 *   - retail-theft: data-bearing charge (outcomes n=1200, sentencing n=700),
 *     verified in the 15.1 walkthrough.
 *   - criminal-trespass: thin-data charge (outcomes n=18, isThinData).
 *   - possession-controlled-substance: outcomes present (n=950), sentencing
 *     distribution deliberately ABSENT; since 35.2 the cell carries a
 *     zero-sentenced index summary (323 convictions, 0 sentenced) — the
 *     ruling-4 fallback-line scenario (35.3).
 *   - simple-assault: outcomes AND sentencing distributions present but
 *     deliberately ABSENT from the sentencing index — the 35.3 absent-arm
 *     stability lock (today's post-Phase-33 page).
 *   - harassment: a real charge with a published run but ZERO aggregate rows —
 *     the charge-only unavailable arm; no judge has results for it, so its
 *     page bakes an empty judge list and any `?judge=` renders the in-page
 *     unavailable notice.
 *   - judge-testina-placeholder: data-bearing judge for retail-theft
 *     (outcomes n=140, sentencing n=85; index cell present since 35.2).
 *   - judge-fakename-example: canonical no-results fixture — both ref rows
 *     exist, zero aggregate rows; never offered by a judge filter (STATIC-2b
 *     pin 4), and `?judge=` naming it renders the in-page unavailable notice.
 *   - dui-general-impairment × judge-samuel-seeddata: success payload with
 *     outcome/sentencing rows but an ABSENT index cell (35.3 absent judge
 *     arm).
 */
export const SLUGS = {
  chargeDataBearing: 'retail-theft',
  chargeThin: 'criminal-trespass',
  chargeZeroSentenced: 'possession-controlled-substance',
  chargeIndexAbsent: 'simple-assault',
  chargeUnavailable: 'harassment',
  chargeUnknown: 'no-such-charge-slug-xyz',
  chargeJudgeIndexAbsent: 'dui-general-impairment',
  judgeDataBearing: 'judge-testina-placeholder',
  judgeNoAggregate: 'judge-fakename-example',
  judgeIndexAbsent: 'judge-samuel-seeddata',
} as const;

// Display names as seeded (used to target autocomplete options), sourced from
// reference-data.ts. Not user-facing copy under the copy-safety policy —
// statutes/charge names and the obviously-fake seed judge names.
export const DISPLAY_NAMES = {
  chargeDataBearing: 'Retail Theft',
  judgeDataBearing: 'Judge Testina Placeholder',
} as const;
