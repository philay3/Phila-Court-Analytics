import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  FETCH_FAILURE_MESSAGE,
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  type ChargeJudgeDataFile,
  type JudgeSpecificResultSuccess,
  type SearchIndexJudge,
} from '@pca/shared';
import { JUDGE_RESULT_COPY } from '../../components/judge-result-copy.js';
import { resetStaticDataCache } from '../../lib/static-data.js';

// `?judge=` is read through useSearchParams; the mock lets each test set it.
const { params } = vi.hoisted(() => ({ params: { current: new URLSearchParams() } }));
vi.mock('next/navigation', () => ({ useSearchParams: () => params.current }));
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const { ChargeResultShell } = await import('./ChargeResultShell.js');

// Invented fixture (tier-1 rules): a fictional offense and a fictional judge.
const CHARGE_SLUG = 'kite-string-tampering';
const JUDGES: SearchIndexJudge[] = [
  { slug: 'judge-ada-quill', displayName: 'Judge Ada Quill', aliases: [] },
];
const PAYLOAD: JudgeSpecificResultSuccess = {
  resultType: 'judge_specific',
  charge: {
    id: '22222222-2222-4222-8222-222222222222',
    slug: CHARGE_SLUG,
    displayName: 'Kite String Tampering',
  },
  judge: {
    id: '33333333-3333-4333-8333-333333333333',
    slug: 'judge-ada-quill',
    displayName: 'Judge Ada Quill',
  },
  geography: 'philadelphia',
  dateRange: { start: '2025-01-01', end: '2026-01-31' },
  lastRefreshed: '2026-02-01T00:00:00.000Z',
  taxonomyVersion: '1.0.0',
  aggregateRunId: '11111111-1111-4111-8111-111111111111',
  judgeSpecific: {
    outcomes: {
      sampleSize: 12,
      thinData: true,
      rows: [{ categoryCode: 'dismissed', displayName: 'Dismissed', count: 12, percentage: 100 }],
    },
    sentencing: { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE },
  },
  baseline: {
    outcomes: {
      sampleSize: 40,
      thinData: false,
      rows: [{ categoryCode: 'dismissed', displayName: 'Dismissed', count: 40, percentage: 100 }],
    },
    sentencing: { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE },
  },
  sentencingIndex: { available: false },
  links: { methodology: '/methodology', definitions: '/definitions' },
};
const FILE: ChargeJudgeDataFile = {
  aggregateRunId: PAYLOAD.aggregateRunId,
  chargeSlug: CHARGE_SLUG,
  judges: { 'judge-ada-quill': PAYLOAD },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function renderShell() {
  return render(
    <ChargeResultShell chargeSlug={CHARGE_SLUG} judges={JUDGES}>
      <div data-testid="charge-only">charge-only view</div>
    </ChargeResultShell>,
  );
}

async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  params.current = new URLSearchParams();
  resetStaticDataCache();
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetStaticDataCache();
});

describe('ChargeResultShell (STATIC-2b pin 3)', () => {
  it('renders only the charge-only children when ?judge= is absent, and fetches nothing', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(FILE)));
    vi.stubGlobal('fetch', fetchMock);
    renderShell();
    await flush();

    expect(screen.getByTestId('charge-only')).toBeInTheDocument();
    expect(screen.queryByTestId('judge-filter-notice')).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('renders the pinned unavailable notice above the charge-only view for an unpaired or unknown judge, without fetching', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(FILE)));
    vi.stubGlobal('fetch', fetchMock);
    params.current = new URLSearchParams('judge=judge-not-paired');
    renderShell();
    await flush();

    const notice = screen.getByTestId('judge-filter-notice');
    expect(notice).toHaveTextContent(JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE);
    expect(
      screen.getByRole('link', { name: JUDGE_RESULT_COPY.removeFilterLinkText }),
    ).toHaveAttribute('href', `/charges/${CHARGE_SLUG}`);
    expect(screen.getByTestId('charge-only')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('fetches the per-charge file once for a paired judge and renders the judge-specific view in place', async () => {
    const fetchMock = vi.fn<(url: string | URL) => Promise<Response>>(() =>
      Promise.resolve(jsonResponse(FILE)),
    );
    vi.stubGlobal('fetch', fetchMock);
    params.current = new URLSearchParams('judge=judge-ada-quill');
    renderShell();

    // Loading line first (the charge-only view stays visible), then the panel.
    expect(screen.getByRole('status')).toHaveTextContent(JUDGE_RESULT_COPY.panelLoading);
    await flush();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(`/data/charges/${CHARGE_SLUG}.json`);
    expect(
      screen.getByRole('heading', { name: JUDGE_RESULT_COPY.sectionJudgeSpecificHeading }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: JUDGE_RESULT_COPY.sectionBaselineHeading }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId('charge-only')).not.toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: JUDGE_RESULT_COPY.removeFilterLinkText }),
    ).toHaveAttribute('href', `/charges/${CHARGE_SLUG}`);
  });

  it('renders the transport-failure notice above the charge-only view when the file cannot be loaded', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('offline'))),
    );
    params.current = new URLSearchParams('judge=judge-ada-quill');
    renderShell();
    await flush();

    expect(screen.getByTestId('judge-filter-notice')).toHaveTextContent(FETCH_FAILURE_MESSAGE);
    expect(screen.getByTestId('charge-only')).toBeInTheDocument();
  });

  it('renders the unavailable notice when the file carries no payload for the judge', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ ...FILE, judges: {} }))),
    );
    params.current = new URLSearchParams('judge=judge-ada-quill');
    renderShell();
    await flush();

    expect(screen.getByTestId('judge-filter-notice')).toHaveTextContent(
      JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
    );
    expect(screen.getByTestId('charge-only')).toBeInTheDocument();
  });
});
