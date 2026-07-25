import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CHARGE_VOLUME_ONLY_MESSAGE, type ChargeOnlyResultVolume } from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { ChargeVolumeView } from './ChargeVolumeView.js';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={typeof href === 'string' ? href : ''} {...rest}>
      {children}
    </a>
  ),
}));

const VOLUME: ChargeOnlyResultVolume = {
  resultType: 'charge_only_volume',
  message: CHARGE_VOLUME_ONLY_MESSAGE,
  charge: {
    id: '00000000-0000-0000-0000-000000000010',
    slug: 'open-lewdness',
    displayName: 'Open Lewdness',
  },
  geography: 'philadelphia',
  dateRange: { start: '2025-01-01', end: '2026-06-30' },
  lastRefreshed: '2026-07-01T12:00:00.000Z',
  taxonomyVersion: '1.0.0',
  aggregateRunId: '00000000-0000-0000-0000-0000000000aa',
  volume: { available: true, chargesSeen: 1234, outcomesRecorded: 0 },
  links: { methodology: '/methodology', definitions: '/definitions' },
};

describe('ChargeVolumeView', () => {
  it('renders identity, the seen count through the pinned template, the message, and links', () => {
    render(<ChargeVolumeView data={VOLUME} />);

    expect(screen.getByRole('heading', { level: 1, name: 'Open Lewdness' })).toBeInTheDocument();
    // The Phase 36 number that replaces the dead end, en-US formatted.
    expect(screen.getByTestId('volume-seen-line')).toHaveTextContent(
      'Charges seen for this offense so far: 1,234. None has a recorded final outcome yet.',
    );
    // Message asserted via the imported @pca/shared constant, never re-typed.
    expect(screen.getByText(CHARGE_VOLUME_ONLY_MESSAGE)).toBeInTheDocument();

    const methodology = screen.getByRole('link', {
      name: CHARGE_RESULT_COPY.methodologyLinkText,
    });
    expect(methodology).toHaveAttribute('href', '/methodology');
    const definitions = screen.getByRole('link', {
      name: CHARGE_RESULT_COPY.definitionsLinkText,
    });
    expect(definitions).toHaveAttribute('href', '/definitions');
  });

  it('never renders any stage-breakdown vocabulary (operator display ruling)', () => {
    const { container } = render(<ChargeVolumeView data={VOLUME} />);
    for (const phrase of ['held for court', 'pending', 'excluded', 'superseded']) {
      expect(container.textContent?.toLowerCase()).not.toContain(phrase);
    }
  });
});
