import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RESULT_DISPLAY_COPY } from '../components/result-display-copy.js';
import AboutPage from './page.js';

// /about is a static server component (no fetch / async), so it renders
// directly under jsdom. These assertions pin the semantic structure and the
// wired-in shared framing — they never re-type disclaimer copy (the
// responsible-use text is proven via the shared RESULT_DISPLAY_COPY constant).

const SECTION_HEADINGS = [
  'What this site is',
  'Where the data comes from',
  'How to read the numbers',
  'Responsible use',
];

const CONTENT_LINKS = [
  { name: 'Methodology', href: '/methodology' },
  { name: 'Definitions', href: '/definitions' },
  { name: 'Data Coverage', href: '/data-coverage' },
];

describe('AboutPage', () => {
  it('renders the page heading (h1)', () => {
    render(<AboutPage />);
    expect(screen.getByRole('heading', { level: 1, name: 'About this site' })).toBeInTheDocument();
  });

  it('renders each section as an h2', () => {
    render(<AboutPage />);
    for (const heading of SECTION_HEADINGS) {
      expect(screen.getByRole('heading', { level: 2, name: heading })).toBeInTheDocument();
    }
  });

  it('renders the shared responsible-use framing', () => {
    render(<AboutPage />);
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseHistorical)).toBeInTheDocument();
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseNotLegalAdvice)).toBeInTheDocument();
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseNotPrediction)).toBeInTheDocument();
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseCasesVary)).toBeInTheDocument();
  });

  it('links to the three content pages', () => {
    render(<AboutPage />);
    for (const { name, href } of CONTENT_LINKS) {
      expect(screen.getByRole('link', { name }).getAttribute('href')).toBe(href);
    }
  });
});
