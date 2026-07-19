import { describe, expect, it } from 'vitest';
import {
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type ChargeOnlyResultResponse,
  type ChargeOnlyResultSuccess,
  type ChargeOnlyResultUnavailable,
} from '@pca/shared';
import type { PublicApiResult } from '../../lib/public-api-client.js';
import { resolveChargeResultState } from './charge-result-state.js';

const CHARGE = {
  id: '00000000-0000-0000-0000-000000000001',
  slug: 'theft',
  displayName: 'Theft',
} as const;

const LINKS = { methodology: '/methodology', definitions: '/definitions' } as const;

const SUCCESS: ChargeOnlyResultSuccess = {
  charge: CHARGE,
  resultType: 'charge_only',
  geography: 'philadelphia',
  dateRange: { start: '2025-01-01', end: '2026-06-30' },
  lastRefreshed: '2026-07-01T12:00:00.000Z',
  taxonomyVersion: '1.0.0',
  aggregateRunId: '00000000-0000-0000-0000-0000000000aa',
  outcomes: {
    sampleSize: 1000,
    thinData: false,
    rows: [
      { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 1000, percentage: 100 },
    ],
  },
  sentencing: {
    available: false,
    message: 'Historical sentencing data is not available for this charge yet.',
  },
  // Task 35.2 type-compatibility only: the absent arm, rendered by 35.3.
  sentencingIndex: { available: false },
  links: LINKS,
};

const UNAVAILABLE: ChargeOnlyResultUnavailable = {
  resultType: 'charge_only_unavailable',
  code: PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
  message: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  charge: CHARGE,
  links: LINKS,
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

describe('resolveChargeResultState', () => {
  it('maps the charge_only 200 arm to the success state', () => {
    const result: PublicApiResult<ChargeOnlyResultResponse> = { ok: true, data: SUCCESS };
    expect(resolveChargeResultState(result)).toEqual({ kind: 'success', data: SUCCESS });
  });

  it('maps the charge_only_unavailable 200 arm to the in-page unavailable state', () => {
    const result: PublicApiResult<ChargeOnlyResultResponse> = { ok: true, data: UNAVAILABLE };
    expect(resolveChargeResultState(result)).toEqual({ kind: 'unavailable', data: UNAVAILABLE });
  });

  it('maps a CHARGE_NOT_FOUND api_error to the not-found state', () => {
    const result = apiError(PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND, 404);
    expect(resolveChargeResultState(result)).toEqual({ kind: 'not-found' });
  });

  it('maps any other api_error code to the generic error state', () => {
    expect(resolveChargeResultState(apiError(PUBLIC_ERROR_CODES.INTERNAL_ERROR, 500))).toEqual({
      kind: 'error',
    });
    expect(resolveChargeResultState(apiError(PUBLIC_ERROR_CODES.RATE_LIMITED, 429))).toEqual({
      kind: 'error',
    });
  });

  it('maps a transport failure to the generic error state', () => {
    const result: PublicApiResult<ChargeOnlyResultResponse> = {
      ok: false,
      error: { kind: 'fetch_failed' },
    };
    expect(resolveChargeResultState(result)).toEqual({ kind: 'error' });
  });
});
