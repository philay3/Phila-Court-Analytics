import { JUDGE_RESULT_NOT_FOUND_MESSAGE } from '@pca/shared';
import { ResultNotFoundView } from '../../../../components/ResultNotFoundView';

/**
 * Judge-route not-found boundary (fix R7b, 2026-07-25). Rendered via
 * `notFound()` with real 404 semantics, replacing the former in-page soft-404.
 * The boundary is prop-less, so the single pinned combination literal covers
 * both not-found reasons (unknown charge, unknown judge); the per-reason
 * literals remain on the API error envelopes. The body reuses the
 * presentational `ResultNotFoundView` shell, imported message, never re-typed.
 */
export default function NotFound() {
  return (
    <div className="mx-auto w-full max-w-article">
      <ResultNotFoundView message={JUDGE_RESULT_NOT_FOUND_MESSAGE} />
    </div>
  );
}
