import { HOME_COPY } from './home-copy';

/*
 * Homepage search surface (task 12.1) — LAYOUT AND COPY ONLY.
 *
 * This is a server component: no 'use client', no state, no event handlers.
 * The <form> has no action and no submit wiring; the inputs are DISABLED
 * presentational placeholders. Disabled inputs cannot be focused or submitted,
 * so pressing Enter never navigates — there is no functional search here.
 *
 * Two regions, both marked with MOUNT comments:
 *   - Charge region  → task 12.2 replaces the disabled <input> with its
 *                      <ChargeSearchInput id="charge-search" />.
 *   - Judge region   → task 12.3 replaces the disabled <input> with its
 *                      <JudgeSearchInput id="judge-search" />.
 * Only the <input> element swaps; the surrounding label + wrapper markup and
 * styling stay, so the 12.2/12.3 swap needs no layout rework.
 */
export function SearchForm() {
  return (
    <section aria-labelledby="search-heading" className="mt-8">
      <h2 id="search-heading" className="sr-only">
        {HOME_COPY.searchHeading}
      </h2>

      <form noValidate className="flex flex-col gap-6">
        {/* Charge region — visually PRIMARY */}
        <div className="rounded-lg border border-line bg-surface p-5">
          <label htmlFor="charge-search" className="block text-lg font-semibold text-ink">
            {HOME_COPY.chargeLabel}
          </label>
          <p id="charge-search-help" className="mt-1 text-sm text-muted">
            {HOME_COPY.chargeHelp}
          </p>
          {/* MOUNT: task 12.2 replaces this disabled placeholder with
              <ChargeSearchInput id="charge-search" />. Keep the id and the
              aria-describedby wiring. */}
          <input
            id="charge-search"
            type="text"
            disabled
            placeholder={HOME_COPY.chargePlaceholder}
            aria-describedby="charge-search-help"
            className="mt-3 w-full rounded-md border border-line bg-canvas px-4 py-3 text-base text-ink placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-70"
          />
        </div>

        {/* Judge region — visually SECONDARY, optional */}
        <div className="rounded-lg border border-line p-4">
          <label htmlFor="judge-search" className="block text-base font-medium text-ink">
            {HOME_COPY.judgeLabel}
          </label>
          <p id="judge-search-help" className="mt-1 text-sm text-muted">
            {HOME_COPY.judgeHelp}
          </p>
          {/* MOUNT: task 12.3 replaces this disabled placeholder with
              <JudgeSearchInput id="judge-search" />. Keep the id and the
              aria-describedby wiring. */}
          <input
            id="judge-search"
            type="text"
            disabled
            placeholder={HOME_COPY.judgePlaceholder}
            aria-describedby="judge-search-help"
            className="mt-3 w-full rounded-md border border-line bg-canvas px-4 py-2.5 text-base text-ink placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-70"
          />
        </div>
      </form>
    </section>
  );
}
