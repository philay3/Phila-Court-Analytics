import { describe, expect, it } from 'vitest';
import {
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type JudgeSpecificResultResponse,
  type JudgeSpecificResultSuccess,
  type JudgeSpecificResultUnavailable,
  type ResultDistributions,
} from '@pca/shared';
import type { PublicApiResult } from '../../../../lib/public-api-client.js';
import { resolveJudgeResultState } from './judge-result-state.js';

const CHARGE = {
  id: '00000000-0000-0000-0000-000000000001',
  slug: 'theft',
  displayName: 'Theft',
} as const;

const JUDGE = {
  id: '00000000-0000-0000-0000-000000000002',
  slug: 'example-judge',
  displayName: 'Example judge',
} as const;

const LINKS = { methodology: '/methodology', definitions: '/definitions' } as const;

const DISTRIBUTIONS: ResultDistributions = {
  outcomes: {
    sampleSize: 14,
    thinData: false,
    rows: [{ categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 14, percentage: 100 }],
  },
  sentencing: {
    available: true,
    sampleSize: 9,
    thinData: false,
    rows: [{ categoryCode: 'probation', displayName: 'Probation', count: 9, percentage: 100 }],
  },
};

const SUCCESS: JudgeSpecificResultSuccess = {
  resultType: 'judge_specific',
  charge: CHARGE,
  judge: JUDGE,
  geography: 'philadelphia',
  dateRange: { start: '2025-01-01', end: '2026-06-30' },
  lastRefreshed: '2026-07-01T12:00:00.000Z',
  taxonomyVersion: '1.0.0',
  aggregateRunId: '00000000-0000-0000-0000-0000000000aa',
  judgeSpecific: DISTRIBUTIONS,
  baseline: DISTRIBUTIONS,
  links: LINKS,
};

const UNAVAILABLE: JudgeSpecificResultUnavailable = {
  resultType: 'judge_specific_unavailable',
  code: PUBLIC_ERROR_CODES.JUDGE_SPECIFIC_RESULT_UNAVAILABLE,
  message: JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  charge: CHARGE,
  judge: JUDGE,
  fallback: { chargeOnlyResultPath: '/api/v1/public/results/charge/theft' },
};

function apiError(
  code: (typeof PUBLIC_ERROR_CODES)[keyof typeof PUBLIC_ERROR_CODES],
  statusCode: number,
) {
  return {
    ok: false as const,
    error: {
      kind: 'api_error' as const,
      statusCode,
      code,
      error: 'error',
      message: 'message',
      requestId: 'req-1',
    },
  };
}

describe('resolveJudgeResultState', () => {
  it('maps the judge_specific 200 arm to the success state', () => {
    const result: PublicApiResult<JudgeSpecificResultResponse> = { ok: true, data: SUCCESS };
    expect(resolveJudgeResultState(result)).toEqual({ kind: 'success', data: SUCCESS });
  });

  it('maps the judge_specific_unavailable 200 arm to the in-page unavailable state', () => {
    const result: PublicApiResult<JudgeSpecificResultResponse> = { ok: true, data: UNAVAILABLE };
    expect(resolveJudgeResultState(result)).toEqual({ kind: 'unavailable', data: UNAVAILABLE });
  });

  it('maps a CHARGE_NOT_FOUND api_error to the not-found state with reason "charge"', () => {
    const result = apiError(PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND, 404);
    expect(resolveJudgeResultState(result)).toEqual({ kind: 'not-found', reason: 'charge' });
  });

  it('maps a JUDGE_NOT_FOUND api_error to the not-found state with reason "judge"', () => {
    const result = apiError(PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND, 404);
    expect(resolveJudgeResultState(result)).toEqual({ kind: 'not-found', reason: 'judge' });
  });

  it('maps a CHARGE_RESULT_UNAVAILABLE 404 api_error to the charge-unavailable state', () => {
    // The judge endpoint delivers "charge resolves but has no publishable
    // aggregate" as a 404 error envelope (not a 200 arm). Task 15.1 walkthrough
    // Finding 1: this must render a designed friendly state, not the generic
    // error boundary.
    const result = apiError(PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE, 404);
    expect(resolveJudgeResultState(result)).toEqual({ kind: 'charge-unavailable' });
  });

  it('maps any other api_error code to the generic error state', () => {
    expect(resolveJudgeResultState(apiError(PUBLIC_ERROR_CODES.INTERNAL_ERROR, 500))).toEqual({
      kind: 'error',
    });
    expect(resolveJudgeResultState(apiError(PUBLIC_ERROR_CODES.RATE_LIMITED, 429))).toEqual({
      kind: 'error',
    });
  });

  it('maps a transport failure to the generic error state', () => {
    const result: PublicApiResult<JudgeSpecificResultResponse> = {
      ok: false,
      error: { kind: 'fetch_failed' },
    };
    expect(resolveJudgeResultState(result)).toEqual({ kind: 'error' });
  });
});
