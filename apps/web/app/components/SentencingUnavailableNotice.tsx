/**
 * Sentencing-unavailable callout (task 13.2, pinned decision 4). Rendered in
 * place of the sentencing distribution when a success payload carries the
 * `sentencing.available === false` arm. The outcome distribution still renders
 * in full; the page never fails wholesale.
 *
 * The body is the pinned `CHARGE_SENTENCING_UNAVAILABLE_MESSAGE` imported from
 * @pca/shared — never re-typed — accompanied by a methodology link whose href
 * comes from the API `links` object.
 */
import Link from 'next/link';
import { CHARGE_SENTENCING_UNAVAILABLE_MESSAGE } from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy';

interface SentencingUnavailableNoticeProps {
  /** Methodology href from the API `links` object (`/methodology`). */
  methodologyHref: string;
}

export function SentencingUnavailableNotice({ methodologyHref }: SentencingUnavailableNoticeProps) {
  return (
    <div role="note" className="space-y-2 rounded-md border border-line bg-surface p-4 text-sm">
      <p className="text-ink">{CHARGE_SENTENCING_UNAVAILABLE_MESSAGE}</p>
      <Link
        href={methodologyHref}
        className="text-accent hover:text-accent-hover hover:underline"
      >
        {CHARGE_RESULT_COPY.methodologyLinkText}
      </Link>
    </div>
  );
}
