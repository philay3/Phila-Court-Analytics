/**
 * Charge-result-unavailable view for the JUDGE route (task 15.1 walkthrough
 * Finding 1). Adapts the 13.2 `ChargeUnavailableView` pattern to the judge
 * route, where the same "charge resolves but no publishable aggregate exists"
 * case arrives NOT as a 200 tagged-union arm but as a 404 CHARGE_RESULT_UNAVAILABLE
 * error envelope — a flat shape that carries the pinned message but no charge
 * identity or `links` object. Because there is no served identity to show, the
 * heading is the generic `chargeUnavailableHeading` (not a charge name), the
 * body is the pinned `CHARGE_RESULT_UNAVAILABLE_MESSAGE` imported from
 * @pca/shared (never re-typed), and the methodology/definitions links use their
 * standing static hrefs — the same pair the charge-only unavailable view shows.
 *
 * Without this view the judge page fell through to its deliberate generic throw
 * and rendered the "Something went wrong" boundary for a designed state. The
 * generic throw remains for genuinely unexpected responses; this is a
 * designed-state mapping placed before it.
 */
import Link from 'next/link';
import { CHARGE_RESULT_UNAVAILABLE_MESSAGE } from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy';

const LINK_CLASS =
  'text-accent hover:underline focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent';

export function JudgeChargeUnavailableView() {
  return (
    <div className="space-y-4">
      <h1>{CHARGE_RESULT_COPY.chargeUnavailableHeading}</h1>
      <p className="text-muted">{CHARGE_RESULT_UNAVAILABLE_MESSAGE}</p>
      <p className="flex flex-wrap gap-4">
        <Link href="/methodology" className={LINK_CLASS}>
          {CHARGE_RESULT_COPY.methodologyLinkText}
        </Link>
        <Link href="/definitions" className={LINK_CLASS}>
          {CHARGE_RESULT_COPY.definitionsLinkText}
        </Link>
      </p>
    </div>
  );
}
