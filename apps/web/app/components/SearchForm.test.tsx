import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { JUDGE_FILTER_HELP_MESSAGE, type SearchIndexAvailable } from '@pca/shared';
import { HOME_COPY } from './home-copy.js';
import { CHARGE_SEARCH_COPY } from './charge-search-copy.js';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { resetStaticDataCache } from '../lib/static-data.js';

const DEBOUNCE_MS = 250;

const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

// Imported after the mock is registered so useRouter resolves to the stub.
const { SearchForm } = await import('./SearchForm.js');

// Invented index: one charge paired with one judge; a second judge with no
// pair for that charge, so scoping is observable (pin 4).
const INDEX: SearchIndexAvailable = {
  available: true,
  aggregateRunId: '11111111-1111-4111-8111-111111111111',
  taxonomyVersion: '1.0.0',
  lastRefreshed: '2026-01-01T00:00:00.000Z',
  charges: [
    { slug: 'alpha-charge', displayName: 'Alpha Charge', aliases: [] },
    { slug: 'gamma-charge', displayName: 'Gamma Charge', aliases: [] },
  ],
  judges: [
    { slug: 'judge-x', displayName: 'Judge X', aliases: [] },
    { slug: 'judge-y', displayName: 'Judge Y', aliases: [] },
  ],
  pairs: [
    { chargeSlug: 'alpha-charge', judgeSlug: 'judge-x' },
    { chargeSlug: 'gamma-charge', judgeSlug: 'judge-y' },
  ],
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
}

async function settleDebounce(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
  });
}

/** Flush the index promise and the paired-judges effect. */
async function flush(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

function combobox(): HTMLInputElement {
  // Two comboboxes share this form (charge + judge); scope by label.
  return screen.getByRole('combobox', { name: HOME_COPY.chargeLabel }) as HTMLInputElement;
}

function judgeCombobox(): HTMLInputElement {
  return screen.getByRole('combobox', { name: HOME_COPY.judgeLabel }) as HTMLInputElement;
}

/** DP-3: the judge region sits behind the disclosure; open it before use. */
function openJudgeDisclosure(): void {
  fireEvent.click(
    screen.getByRole('button', { name: CHARGE_RESULT_COPY.judgeDisclosureTriggerText }),
  );
}

async function commitCharge(query: string, name: string): Promise<void> {
  fireEvent.change(combobox(), { target: { value: query } });
  await settleDebounce();
  fireEvent.click(screen.getByText(name));
  await flush();
}

async function commitJudge(name: string): Promise<void> {
  fireEvent.change(judgeCombobox(), { target: { value: 'judge' } });
  await settleDebounce();
  fireEvent.click(screen.getByText(name));
}

function submit(): void {
  fireEvent.click(screen.getByRole('button', { name: CHARGE_SEARCH_COPY.submitButton }));
}

beforeEach(() => {
  vi.useFakeTimers();
  push.mockClear();
  resetStaticDataCache();
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(jsonResponse(INDEX))),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  resetStaticDataCache();
});

describe('SearchForm charge submission', () => {
  it('keyboard path: type, ArrowDown, Enter commits, Enter submits to /charges/[slug]', async () => {
    render(<SearchForm />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();

    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' }); // commits the active option (list open)
    expect(input.value).toBe('Alpha Charge');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();

    // List is closed now: Enter submits the form.
    fireEvent.submit(input.closest('form')!);
    expect(push).toHaveBeenCalledWith('/charges/alpha-charge');
  });

  it('mouse path: a committed charge plus a submit-button click navigates', async () => {
    render(<SearchForm />);
    await commitCharge('alpha', 'Alpha Charge');
    submit();
    expect(push).toHaveBeenCalledWith('/charges/alpha-charge');
  });

  it('Enter with the list open but no active option does nothing', async () => {
    render(<SearchForm />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    fireEvent.keyDown(input, { key: 'Enter' });

    expect(push).not.toHaveBeenCalled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(input.value).toBe('alpha');
  });

  it('submitting with no committed charge shows the hint and does not navigate', async () => {
    render(<SearchForm />);
    submit();
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByText(CHARGE_SEARCH_COPY.submitHint)).toBeInTheDocument();
  });

  it('never calls the API: the only request is the index file', async () => {
    render(<SearchForm />);
    await commitCharge('alpha', 'Alpha Charge');
    openJudgeDisclosure();
    await commitJudge('Judge X');
    submit();
    const urls = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls.map((call) =>
      String(call[0]),
    );
    expect(urls).toEqual(['/data/search-index.json']);
  });
});

describe('SearchForm judge scoping and submission (STATIC-2b pin 4)', () => {
  it('the open judge region renders exactly the sanctioned shared help line (DP-5 AC1)', () => {
    render(<SearchForm />);
    openJudgeDisclosure();
    expect(screen.getByText(JUDGE_FILTER_HELP_MESSAGE)).toBeInTheDocument();
    expect(document.getElementById('judge-search-help')?.textContent).toBe(
      JUDGE_FILTER_HELP_MESSAGE,
    );
  });

  it('the judge field is disabled until a charge is committed', async () => {
    render(<SearchForm />);
    openJudgeDisclosure();
    expect(judgeCombobox()).toBeDisabled();

    await commitCharge('alpha', 'Alpha Charge');
    expect(judgeCombobox()).not.toBeDisabled();
  });

  it('offers only judges paired with the committed charge', async () => {
    render(<SearchForm />);
    await commitCharge('alpha', 'Alpha Charge');
    openJudgeDisclosure();

    fireEvent.change(judgeCombobox(), { target: { value: 'judge' } });
    await settleDebounce();
    expect(screen.getByText('Judge X')).toBeInTheDocument();
    expect(screen.queryByText('Judge Y')).not.toBeInTheDocument();
  });

  it('charge + judge committed routes to /charges/[chargeSlug]?judge=[judgeSlug]', async () => {
    render(<SearchForm />);
    await commitCharge('alpha', 'Alpha Charge');
    openJudgeDisclosure();
    await commitJudge('Judge X');
    submit();
    expect(push).toHaveBeenCalledWith('/charges/alpha-charge?judge=judge-x');
  });

  it('changing the charge clears the staged judge and re-scopes the field', async () => {
    render(<SearchForm />);
    await commitCharge('alpha', 'Alpha Charge');
    openJudgeDisclosure();
    await commitJudge('Judge X');
    expect(judgeCombobox().value).toBe('Judge X');

    await commitCharge('gamma', 'Gamma Charge');
    // The remounted judge field is empty and now scoped to the new charge.
    expect(judgeCombobox().value).toBe('');
    fireEvent.change(judgeCombobox(), { target: { value: 'judge' } });
    await settleDebounce();
    expect(screen.getByText('Judge Y')).toBeInTheDocument();
    expect(screen.queryByText('Judge X')).not.toBeInTheDocument();

    submit();
    expect(push).toHaveBeenCalledWith('/charges/gamma-charge');
  });

  it('editing the judge after a commit clears it; a later submit routes charge-only', async () => {
    render(<SearchForm />);
    await commitCharge('alpha', 'Alpha Charge');
    openJudgeDisclosure();
    await commitJudge('Judge X');
    fireEvent.change(judgeCombobox(), { target: { value: 'Judge X extra' } });

    submit();
    expect(push).toHaveBeenCalledWith('/charges/alpha-charge');
    expect(push).not.toHaveBeenCalledWith('/charges/alpha-charge?judge=judge-x');
  });
});
