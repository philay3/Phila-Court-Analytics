/**
 * Judge-unavailable view (task 13.3, pinned decision 4). Renders the HTTP 200
 * `judge_specific_unavailable` arm IN PAGE — it is a content branch of the
 * page, not an error page. The charge and judge both resolve, but no
 * judge-specific aggregate exists yet.
 *
 * It shows the charge and judge identities as served, the pinned
 * `JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE` imported from @pca/shared (never
 * re-typed, and NOT read off `data.message`), and a prominent link to the
 * charge-only result page. It renders NO distribution sections and surfaces no
 * internal reasons (the `code` is never displayed). Presentational only.
 */
import Link from 'next/link';
import {
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  type JudgeSpecificResultUnavailable,
} from '@pca/shared';
import { JUDGE_RESULT_COPY } from './judge-result-copy';

interface JudgeUnavailableViewProps {
  data: JudgeSpecificResultUnavailable;
}

const LINK_CLASS = 'text-accent hover:text-accent-hover hover:underline';

export function JudgeUnavailableView({ data }: JudgeUnavailableViewProps) {
  const { charge, judge } = data;
  return (
    <div className="space-y-4">
      <h1>{charge.displayName}</h1>
      <p className="text-base font-semibold text-ink">{judge.displayName}</p>
      <p className="text-muted">{JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE}</p>
      <Link href={`/charges/${charge.slug}`} className={LINK_CLASS}>
        {JUDGE_RESULT_COPY.removeFilterLinkText}
      </Link>
    </div>
  );
}
