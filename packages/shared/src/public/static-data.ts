import type { JudgeSpecificResultSuccess } from './judge-result.js';

/**
 * Static-export data files (task STATIC-2b, pin 11.6). The build script writes
 * them under a top-level `data/` folder of the export (never under `public/`,
 * never committed); the web reads them from the browser. The folder name is
 * pinned so nothing collides with Next's per-route output directories.
 *
 *   /data/search-index.json       — the search-index response body (available arm)
 *   /data/charges/<slug>.json     — one file per charge that has judge-specific
 *                                   results: the served `judge_specific`
 *                                   payloads keyed by judge slug, plus the
 *                                   pinned run id
 */
export const STATIC_DATA_DIR = 'data';
export const SEARCH_INDEX_DATA_PATH = `/${STATIC_DATA_DIR}/search-index.json`;

export function chargeJudgeDataPath(chargeSlug: string): string {
  return `/${STATIC_DATA_DIR}/charges/${encodeURIComponent(chargeSlug)}.json`;
}

export interface ChargeJudgeDataFile {
  /** The run every payload in this file was served from. */
  aggregateRunId: string;
  chargeSlug: string;
  /** `judge_specific` payloads keyed by judge slug — only judges with results. */
  judges: Record<string, JudgeSpecificResultSuccess>;
}
