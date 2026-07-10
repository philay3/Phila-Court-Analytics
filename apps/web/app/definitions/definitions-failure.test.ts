import { describe, expect, it } from 'vitest';
import { FETCH_FAILURE_MESSAGE, PUBLIC_ERROR_MESSAGES } from '@pca/shared';
import { definitionsFailureMessage } from './definitions-failure.js';

describe('definitionsFailureMessage', () => {
  it('maps an api_error to the shared catalog message for its code', () => {
    expect(
      definitionsFailureMessage({
        kind: 'api_error',
        statusCode: 500,
        code: 'INTERNAL_ERROR',
        error: 'Internal Server Error',
        message: 'internal detail that must never be shown',
        requestId: 'req-123',
      }),
    ).toBe(PUBLIC_ERROR_MESSAGES.INTERNAL_ERROR);
  });

  it('maps a fetch_failed transport failure to the shared fetch-failure message', () => {
    expect(definitionsFailureMessage({ kind: 'fetch_failed' })).toBe(FETCH_FAILURE_MESSAGE);
  });

  it('never surfaces the API-provided message or request detail', () => {
    const message = definitionsFailureMessage({
      kind: 'api_error',
      statusCode: 500,
      code: 'INTERNAL_ERROR',
      error: 'Internal Server Error',
      message: 'internal detail that must never be shown',
      requestId: 'req-123',
    });
    expect(message).not.toContain('internal detail');
    expect(message).not.toContain('req-123');
  });
});
