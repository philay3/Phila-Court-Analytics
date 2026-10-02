import {
  SEARCH_INDEX_DATA_PATH,
  chargeJudgeDataPath,
  type ChargeJudgeDataFile,
  type SearchIndexAvailable,
  type SearchIndexResponse,
} from '@pca/shared';
import { fetchPublicPath, type PublicApiResult } from './public-api-client';

/**
 * Browser-side readers for the static export's data files (task STATIC-2b,
 * pins 3, 4, 6). The build script writes `/data/search-index.json` and one
 * `/data/charges/<slug>.json` per charge with judge-specific results; the
 * comboboxes and the in-page judge panel read them lazily — on first
 * interaction, or on load when `?judge=` is present — and never call the API.
 *
 * Each file is fetched at most once per page: the promise is memoised at
 * module level, and a failed load clears its slot so a later interaction can
 * retry. Results use the public-API client's tagged union, so the consuming
 * components keep their existing failure arms (FETCH_FAILURE_MESSAGE or the
 * catalog message).
 */

const FETCH_FAILED: PublicApiResult<never> = { ok: false, error: { kind: 'fetch_failed' } };

let indexPromise: Promise<PublicApiResult<SearchIndexAvailable>> | null = null;
const chargeFilePromises = new Map<string, Promise<PublicApiResult<ChargeJudgeDataFile>>>();

export function loadSearchIndex(): Promise<PublicApiResult<SearchIndexAvailable>> {
  if (indexPromise === null) {
    indexPromise = fetchPublicPath<SearchIndexResponse>(SEARCH_INDEX_DATA_PATH).then((result) => {
      if (!result.ok) {
        indexPromise = null;
        return result;
      }
      if (!result.data.available) {
        // The build never writes an unavailable arm; treat one as a failed load.
        indexPromise = null;
        return FETCH_FAILED;
      }
      return { ok: true, data: result.data };
    });
  }
  return indexPromise;
}

export function loadChargeJudgeData(
  chargeSlug: string,
): Promise<PublicApiResult<ChargeJudgeDataFile>> {
  let promise = chargeFilePromises.get(chargeSlug);
  if (!promise) {
    promise = fetchPublicPath<ChargeJudgeDataFile>(chargeJudgeDataPath(chargeSlug)).then(
      (result) => {
        if (!result.ok) {
          chargeFilePromises.delete(chargeSlug);
        }
        return result;
      },
    );
    chargeFilePromises.set(chargeSlug, promise);
  }
  return promise;
}

/** Test seam: forget every memoised file. */
export function resetStaticDataCache(): void {
  indexPromise = null;
  chargeFilePromises.clear();
}
