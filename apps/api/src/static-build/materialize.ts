import type { FastifyInstance } from 'fastify';
import type {
  ChargeJudgeDataFile,
  ChargeOnlyResultResponse,
  DataCoverageResponse,
  JudgeSpecificResultResponse,
  SearchIndexAvailable,
  SearchIndexResponse,
} from '@pca/shared';
import { assertPinnedRunId, shortRunId } from './guards.js';

/**
 * Materialization (task STATIC-2b, pin 11.4): inject every public response the
 * export needs through the in-process Fastify app and keep the raw bodies —
 * byte-identical API output — keyed by path, plus the per-charge judge files.
 * Fail closed on any non-200, any `available: false`, any unexpected
 * `resultType`, and any `aggregateRunId` other than the pinned one.
 */

export const PUBLIC_PREFIX = '/api/v1/public';

const CHARGE_ARMS = new Set(['charge_only', 'charge_only_volume', 'charge_only_unavailable']);

export interface Materialized {
  /** Exact API path → raw JSON body, as the API serialized it. */
  responses: Map<string, string>;
  index: SearchIndexAvailable;
  /** chargeSlug → the file the export will carry under data/charges/. */
  chargeJudgeFiles: Map<string, ChargeJudgeDataFile>;
  counts: { charges: number; pairs: number; chargesWithPairs: number; injected: number };
}

interface Injected<T> {
  status: number;
  raw: string;
  body: T;
}

async function inject<T>(app: FastifyInstance, path: string): Promise<Injected<T>> {
  const res = await app.inject({ method: 'GET', url: path });
  let body: T;
  try {
    body = res.json<T>();
  } catch {
    throw new Error(`${path} returned a non-JSON body (status ${res.statusCode}).`);
  }
  return { status: res.statusCode, raw: res.payload, body };
}

function require200<T>(path: string, hit: Injected<T>): T {
  if (hit.status !== 200) {
    const code = (hit.body as { code?: string } | null)?.code ?? '?';
    throw new Error(`${path} answered ${hit.status} (${code}); the export needs a 200 here.`);
  }
  return hit.body;
}

/** Step 11.3's last check: data-coverage must serve an active run; its id is pinned. */
export async function pinPublishedRun(
  app: FastifyInstance,
): Promise<{ runId: string; path: string; raw: string }> {
  const path = `${PUBLIC_PREFIX}/data-coverage`;
  const hit = await inject<DataCoverageResponse>(app, path);
  const body = require200(path, hit);
  if (!body.coverage.available) {
    throw new Error(
      'data-coverage reports no active published run (available: false); nothing to export.',
    );
  }
  return { runId: body.coverage.aggregateRunId, path, raw: hit.raw };
}

export async function materializePublicApi(
  app: FastifyInstance,
  pinnedRunId: string,
  dataCoverage: { path: string; raw: string },
  log: (line: string) => void,
): Promise<Materialized> {
  const responses = new Map<string, string>();
  let injected = 1; // data-coverage, already injected by pinPublishedRun
  responses.set(dataCoverage.path, dataCoverage.raw);

  // The enumeration itself.
  const indexPath = `${PUBLIC_PREFIX}/search-index`;
  const indexHit = await inject<SearchIndexResponse>(app, indexPath);
  injected += 1;
  const indexBody = require200(indexPath, indexHit);
  if (!indexBody.available) {
    throw new Error('search-index reports available: false; nothing to enumerate.');
  }
  assertPinnedRunId(pinnedRunId, indexBody.aggregateRunId, 'search-index');
  responses.set(indexPath, indexHit.raw);

  // The static content endpoints and the directory.
  for (const name of ['charges', 'definitions', 'methodology']) {
    const path = `${PUBLIC_PREFIX}/${name}`;
    const hit = await inject<{ available?: boolean }>(app, path);
    injected += 1;
    const body = require200(path, hit);
    if (body.available === false) {
      throw new Error(`${path} reports available: false; refusing to bake an unavailable arm.`);
    }
    responses.set(path, hit.raw);
  }

  // Every charge page's payload.
  for (const charge of indexBody.charges) {
    const path = `${PUBLIC_PREFIX}/results/charge/${encodeURIComponent(charge.slug)}`;
    const hit = await inject<ChargeOnlyResultResponse>(app, path);
    injected += 1;
    const body = require200(path, hit);
    if (!CHARGE_ARMS.has(body.resultType)) {
      throw new Error(`${path} served unexpected resultType "${String(body.resultType)}".`);
    }
    if ('aggregateRunId' in body) {
      assertPinnedRunId(pinnedRunId, body.aggregateRunId, path);
    }
    responses.set(path, hit.raw);
  }
  log(`materialized ${indexBody.charges.length} charge results`);

  // Every pair's payload, folded into per-charge judge files.
  const chargeJudgeFiles = new Map<string, ChargeJudgeDataFile>();
  let done = 0;
  for (const pair of indexBody.pairs) {
    const path =
      `${PUBLIC_PREFIX}/results/charge/${encodeURIComponent(pair.chargeSlug)}` +
      `/judge/${encodeURIComponent(pair.judgeSlug)}`;
    const hit = await inject<JudgeSpecificResultResponse>(app, path);
    injected += 1;
    const body = require200(path, hit);
    if (body.resultType !== 'judge_specific') {
      throw new Error(
        `${path} served resultType "${body.resultType}" for a pair the index lists as having a result.`,
      );
    }
    assertPinnedRunId(pinnedRunId, body.aggregateRunId, path);
    let file = chargeJudgeFiles.get(pair.chargeSlug);
    if (!file) {
      file = { aggregateRunId: pinnedRunId, chargeSlug: pair.chargeSlug, judges: {} };
      chargeJudgeFiles.set(pair.chargeSlug, file);
    }
    file.judges[pair.judgeSlug] = body;
    done += 1;
    if (done % 500 === 0) {
      log(`materialized ${done} / ${indexBody.pairs.length} pair results`);
    }
  }
  log(
    `materialized ${indexBody.pairs.length} pair results into ${chargeJudgeFiles.size} charge files (run ${shortRunId(pinnedRunId)})`,
  );

  return {
    responses,
    index: indexBody,
    chargeJudgeFiles,
    counts: {
      charges: indexBody.charges.length,
      pairs: indexBody.pairs.length,
      chargesWithPairs: chargeJudgeFiles.size,
      injected,
    },
  };
}
