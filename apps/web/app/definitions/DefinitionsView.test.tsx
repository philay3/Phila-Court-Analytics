import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import type { DefinitionEntry, DefinitionsResponse } from '@pca/shared';
import { DefinitionsView, DefinitionsErrorState } from './DefinitionsView.js';
import { DEFINITIONS_COPY } from './definitions-copy.js';
import { definitionAnchor, definitionAnchorId } from '../lib/definition-anchor.js';

// Fixtures typed straight from @pca/shared — no local/mock shapes.
const OUTCOMES: DefinitionEntry[] = [
  {
    code: 'guilty_plea',
    displayName: 'Guilty plea',
    definition: 'The defendant pleaded guilty to the charge.',
    sortOrder: 0,
  },
  {
    code: 'dismissed',
    displayName: 'Dismissed',
    definition: 'The charge was dismissed.',
    sortOrder: 1,
  },
  {
    code: 'acquittal',
    displayName: 'Acquittal',
    definition: 'The defendant was found not guilty.',
    sortOrder: 2,
  },
];

const SENTENCING: DefinitionEntry[] = [
  {
    code: 'probation',
    displayName: 'Probation',
    definition: 'A period of court supervision in the community.',
    sortOrder: 0,
  },
  {
    code: 'incarceration',
    displayName: 'Incarceration',
    definition: 'A term of confinement.',
    sortOrder: 1,
  },
];

const RESPONSE: DefinitionsResponse = {
  taxonomyVersion: '2026.07.01',
  outcomes: OUTCOMES,
  sentencing: SENTENCING,
};

describe('DefinitionsView', () => {
  it('renders every outcome and sentencing category with its display name and definition', () => {
    render(<DefinitionsView data={RESPONSE} />);

    for (const entry of [...OUTCOMES, ...SENTENCING]) {
      expect(
        screen.getByRole('heading', { level: 3, name: entry.displayName }),
      ).toBeInTheDocument();
      expect(screen.getByText(entry.definition)).toBeInTheDocument();
    }
  });

  it('renders both section headings under the page heading (h1 → h2 → h3 hierarchy)', () => {
    render(<DefinitionsView data={RESPONSE} />);

    expect(
      screen.getByRole('heading', { level: 1, name: DEFINITIONS_COPY.heading }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: DEFINITIONS_COPY.outcomeSectionHeading }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: DEFINITIONS_COPY.sentencingSectionHeading }),
    ).toBeInTheDocument();
  });

  it('renders categories in served order — the fixture order is NOT re-sorted', () => {
    const { container } = render(<DefinitionsView data={RESPONSE} />);

    const outcomeIds = [...container.querySelectorAll('h3')]
      .map((h) => h.id)
      .filter((id) => id.startsWith('outcome-'));
    expect(outcomeIds).toEqual(OUTCOMES.map((entry) => definitionAnchorId('outcome', entry.code)));
  });

  it('gives every entry a stable element id present in the rendered markup', () => {
    const { container } = render(<DefinitionsView data={RESPONSE} />);

    for (const entry of OUTCOMES) {
      expect(
        container.querySelector(`#${definitionAnchorId('outcome', entry.code)}`),
      ).not.toBeNull();
    }
    for (const entry of SENTENCING) {
      expect(
        container.querySelector(`#${definitionAnchorId('sentencing', entry.code)}`),
      ).not.toBeNull();
    }
  });

  // AC 4: the 13.1 result-page links target `definitionAnchor(kind, code)`; here
  // we prove those fragments resolve to a live element on this page, per
  // distribution type.
  it('resolves the 13.1 outcome definition link fragment to a live element', () => {
    const { container } = render(<DefinitionsView data={RESPONSE} />);

    const fragment = definitionAnchor('outcome', 'guilty_plea').split('#')[1]!;
    const target = container.querySelector(`#${fragment}`);
    expect(target).not.toBeNull();
    expect(within(target as HTMLElement).getByText('Guilty plea')).toBeInTheDocument();
  });

  it('resolves the 13.1 sentencing definition link fragment to a live element', () => {
    const { container } = render(<DefinitionsView data={RESPONSE} />);

    const fragment = definitionAnchor('sentencing', 'probation').split('#')[1]!;
    const target = container.querySelector(`#${fragment}`);
    expect(target).not.toBeNull();
    expect(within(target as HTMLElement).getByText('Probation')).toBeInTheDocument();
  });

  it('displays the taxonomy version from the response', () => {
    render(<DefinitionsView data={RESPONSE} />);

    expect(
      screen.getByText(`${DEFINITIONS_COPY.taxonomyVersionLabel}: ${RESPONSE.taxonomyVersion}`),
    ).toBeInTheDocument();
  });
});

describe('DefinitionsErrorState', () => {
  it('renders the error heading and the supplied shared message, with no internal detail', () => {
    const message = "We couldn't reach the server. Please check your connection and try again.";
    render(<DefinitionsErrorState message={message} />);

    expect(
      screen.getByRole('heading', { level: 1, name: DEFINITIONS_COPY.errorHeading }),
    ).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(message);
  });
});
