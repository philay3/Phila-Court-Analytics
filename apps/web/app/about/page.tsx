import type { Metadata } from 'next';
import Link from 'next/link';
import { ResponsibleUseNotice } from '../components/ResponsibleUseNotice';

/**
 * About route (task 14.3). A static server component — unlike the 14.1/14.2
 * content pages it performs no data fetch, so there is no View split and no
 * loading/error state. All user-facing copy is inline JSX; the app/-walking
 * copy guard scans this file's contents automatically (test/copy-guard.test.ts).
 *
 * The Responsible Use section renders the shared <ResponsibleUseNotice />
 * (the four framing statements from RESULT_DISPLAY_COPY) rather than re-typing
 * any disclaimer text; the only newly authored disclaimer-adjacent sentence is
 * the required attorney-consultation line that follows it.
 *
 * Layout tokens mirror MethodologyView: single-column, mobile-first, semantic
 * hierarchy (one h1, one h2 per section). Site-wide noindex is inherited from
 * the root layout, unchanged.
 */
export const metadata: Metadata = {
  title: 'About this site',
};

const LINK_CLASS = 'text-accent hover:text-accent-hover hover:underline';

export default function AboutPage() {
  return (
    <div className="mx-auto flex w-full max-w-article flex-col gap-10 desktop:gap-12">
      <header>
        <h1>About this site</h1>
      </header>

      <section className="space-y-3">
        <h2 className="font-serif text-xl font-semibold text-ink">What this site is</h2>
        <p className="leading-relaxed text-body">
          This site presents historical aggregate outcomes from Philadelphia criminal court cases.
          Users can search by criminal charge and, optionally, filter by judge to see how cases
          involving that charge have historically been resolved — including outcome distributions
          and, where available, sentencing distributions.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl font-semibold text-ink">Where the data comes from</h2>
        <p className="leading-relaxed text-body">
          The underlying information comes from public court docket sheets published by the
          Pennsylvania Unified Judicial System. Docket information is parsed, normalized, and
          aggregated before anything appears on this site; records that cannot be read reliably are
          excluded automatically. Only aggregate statistics are published here: no individual case
          records, docket numbers, or defendant information are available through this site. For
          details on scope, date ranges, and known limitations, see the Data Coverage page.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl font-semibold text-ink">How to read the numbers</h2>
        <p className="leading-relaxed text-body">
          Every figure on this site shows its sample size and date range. Small samples are flagged
          so they are not over-read. Results are historical distributions of past cases — they
          describe what has happened, not what will happen in any individual case. See the
          Methodology page for how figures are produced and the Definitions page for what each
          category means.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-xl font-semibold text-ink">Responsible use</h2>
        <ResponsibleUseNotice />
        <p className="leading-relaxed text-body">
          If you are facing criminal charges, consult a licensed attorney about your specific
          situation.
        </p>
      </section>

      <nav aria-label="Content pages" className="flex flex-wrap gap-4">
        <Link href="/methodology" className={LINK_CLASS}>
          Methodology
        </Link>
        <Link href="/definitions" className={LINK_CLASS}>
          Definitions
        </Link>
        <Link href="/data-coverage" className={LINK_CLASS}>
          Data Coverage
        </Link>
      </nav>
    </div>
  );
}
