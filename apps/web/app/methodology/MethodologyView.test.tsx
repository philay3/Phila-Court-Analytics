import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { METHODOLOGY_SECTION_KEYS, type MethodologyResponse } from '@pca/shared';
import { MethodologyView, MethodologyErrorState } from './MethodologyView.js';
import { METHODOLOGY_COPY } from './methodology-copy.js';
import Loading from './loading.js';

// Fixture typed straight from @pca/shared — no local/mock shapes. Each section
// gets a distinctive heading/body so verbatim rendering is provable per key.
const RESPONSE: MethodologyResponse = {
  sections: Object.fromEntries(
    METHODOLOGY_SECTION_KEYS.map((key) => [
      key,
      { heading: `Heading for ${key}`, body: `Body copy for ${key}.` },
    ]),
  ) as MethodologyResponse['sections'],
};

describe('MethodologyView', () => {
  it('renders the page heading (h1)', () => {
    render(<MethodologyView data={RESPONSE} />);
    expect(
      screen.getByRole('heading', { level: 1, name: METHODOLOGY_COPY.heading }),
    ).toBeInTheDocument();
  });

  it('renders every served section heading (h2) and body verbatim', () => {
    render(<MethodologyView data={RESPONSE} />);

    for (const key of METHODOLOGY_SECTION_KEYS) {
      const section = RESPONSE.sections[key];
      expect(screen.getByRole('heading', { level: 2, name: section.heading })).toBeInTheDocument();
      expect(screen.getByText(section.body)).toBeInTheDocument();
    }
  });

  it('renders sections in the served presentation order (not re-sorted)', () => {
    const { container } = render(<MethodologyView data={RESPONSE} />);

    const renderedHeadings = [...container.querySelectorAll('h2')].map((h) => h.textContent);
    expect(renderedHeadings).toEqual(
      METHODOLOGY_SECTION_KEYS.map((key) => RESPONSE.sections[key].heading),
    );
  });
});

describe('MethodologyErrorState', () => {
  it('renders the error heading and the supplied shared message, with no internal detail', () => {
    const message = "We couldn't reach the server. Please check your connection and try again.";
    render(<MethodologyErrorState message={message} />);

    expect(
      screen.getByRole('heading', { level: 1, name: METHODOLOGY_COPY.errorHeading }),
    ).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(message);
  });
});

describe('methodology loading state', () => {
  it('renders a neutral in-flight status message', () => {
    render(<Loading />);
    expect(screen.getByRole('status')).toHaveTextContent(METHODOLOGY_COPY.loadingMessage);
  });
});
