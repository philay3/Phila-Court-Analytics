import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import type { ChargeSearchResult, JudgeSearchResult } from '@pca/shared';
import { HOME_COPY } from './home-copy.js';
import { CHARGE_SEARCH_COPY } from './charge-search-copy.js';

const DEBOUNCE_MS = 250;

const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}));

// Imported after the mock is registered so useRouter resolves to the stub.
const { SearchForm } = await import('./SearchForm.js');

const ALPHA: ChargeSearchResult = {
  id: '11111111-1111-1111-1111-111111111111',
  slug: 'alpha-charge',
  displayName: 'Alpha Charge',
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

function combobox(): HTMLInputElement {
  // Two comboboxes share this form (charge + judge, task 12.3); scope the
  // charge query by its label so the bare role query is not ambiguous.
  return screen.getByRole('combobox', { name: HOME_COPY.chargeLabel }) as HTMLInputElement;
}

beforeEach(() => {
  vi.useFakeTimers();
  push.mockClear();
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(jsonResponse({ results: [ALPHA] }))),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('SearchForm charge submission', () => {
  it('keyboard path: type, ArrowDown, Enter commits, Enter submits to /charges/[slug]', async () => {
    render(<SearchForm />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();

    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' }); // commits the active option (list open)
    expect(input.value).toBe(ALPHA.displayName);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();

    // List is closed now: Enter submits the form.
    fireEvent.submit(input.closest('form')!);
    expect(push).toHaveBeenCalledWith(`/charges/${ALPHA.slug}`);
  });

  it('mouse path: a committed charge plus a submit-button click navigates', async () => {
    render(<SearchForm />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();
    fireEvent.click(screen.getByText(ALPHA.displayName)); // commit via mouse

    fireEvent.click(screen.getByRole('button', { name: CHARGE_SEARCH_COPY.submitButton }));
    expect(push).toHaveBeenCalledWith(`/charges/${ALPHA.slug}`);
  });

  it('Enter with the list open but no active option does nothing', async () => {
    render(<SearchForm />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    // No ArrowDown: no active option. Enter must not commit, submit, or hint.
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(push).not.toHaveBeenCalled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(input.value).toBe('alpha');
  });

  it('submitting with no committed charge shows the hint and does not navigate', async () => {
    render(<SearchForm />);

    fireEvent.click(screen.getByRole('button', { name: CHARGE_SEARCH_COPY.submitButton }));

    expect(push).not.toHaveBeenCalled();
    expect(screen.getByText(CHARGE_SEARCH_COPY.submitHint)).toBeInTheDocument();
  });
});

describe('SearchForm judge submission matrix', () => {
  const JUDGE: JudgeSearchResult = {
    id: '33333333-3333-3333-3333-333333333333',
    slug: 'judge-x',
    displayName: 'Judge X',
  };

  /** Route charge-search to a charge result and judge-search to a judge result. */
  function branchingFetch() {
    return vi.fn((url: string) => {
      const body = String(url).includes('/judges/search')
        ? { results: [JUDGE] }
        : { results: [ALPHA] };
      return Promise.resolve(jsonResponse(body));
    });
  }

  function judgeCombobox(): HTMLInputElement {
    return screen.getByRole('combobox', { name: HOME_COPY.judgeLabel }) as HTMLInputElement;
  }

  async function commitCharge(): Promise<void> {
    fireEvent.change(combobox(), { target: { value: 'alpha' } });
    await settleDebounce();
    fireEvent.click(screen.getByText(ALPHA.displayName));
  }

  async function commitJudge(): Promise<void> {
    fireEvent.change(judgeCombobox(), { target: { value: 'judge' } });
    await settleDebounce();
    fireEvent.click(screen.getByText(JUDGE.displayName));
  }

  function submit(): void {
    fireEvent.click(screen.getByRole('button', { name: CHARGE_SEARCH_COPY.submitButton }));
  }

  it('charge + judge committed routes to /charges/[chargeSlug]/judge/[judgeSlug]', async () => {
    vi.stubGlobal('fetch', branchingFetch());
    render(<SearchForm />);

    await commitCharge();
    await commitJudge();
    submit();

    expect(push).toHaveBeenCalledWith(`/charges/${ALPHA.slug}/judge/${JUDGE.slug}`);
  });

  it('judge committed with no charge shows the hint, does not navigate, and preserves the judge commit', async () => {
    vi.stubGlobal('fetch', branchingFetch());
    render(<SearchForm />);

    await commitJudge();
    submit();

    expect(push).not.toHaveBeenCalled();
    expect(screen.getByText(CHARGE_SEARCH_COPY.submitHint)).toBeInTheDocument();
    expect(judgeCombobox().value).toBe(JUDGE.displayName);

    // The judge commit survived the hint path: committing a charge and
    // submitting now routes to the combined path, not charge-only.
    await commitCharge();
    submit();
    expect(push).toHaveBeenCalledWith(`/charges/${ALPHA.slug}/judge/${JUDGE.slug}`);
  });

  it('editing the judge after a commit clears it; a later charge-only submit routes charge-only', async () => {
    vi.stubGlobal('fetch', branchingFetch());
    render(<SearchForm />);

    await commitJudge();
    // Edit after commit clears the judge commit (shared combobox behavior).
    fireEvent.change(judgeCombobox(), { target: { value: `${JUDGE.displayName} extra` } });

    await commitCharge();
    submit();

    expect(push).toHaveBeenCalledWith(`/charges/${ALPHA.slug}`);
    expect(push).not.toHaveBeenCalledWith(`/charges/${ALPHA.slug}/judge/${JUDGE.slug}`);
  });
});
