import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'Philadelphia Court Outcomes',
    template: '%s — Philadelphia Court Outcomes',
  },
  description: 'Historical aggregate outcomes in Philadelphia criminal court cases.',
  // Deliberate site-wide noindex: per the front-end spec, indexing is opt-in
  // after review. Revisit at launch readiness.
  robots: {
    index: false,
    follow: false,
  },
};

const NAV_LINKS = [
  { href: '/', label: 'Home' },
  { href: '/methodology', label: 'Methodology' },
  { href: '/definitions', label: 'Definitions' },
  { href: '/data-coverage', label: 'Data Coverage' },
  { href: '/about', label: 'About' },
] as const;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-line bg-surface px-6 py-4">
          <p className="mb-2 text-lg font-semibold text-ink">Philadelphia Court Outcomes</p>
          <nav aria-label="Main navigation">
            <ul className="flex flex-wrap gap-4">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-accent hover:underline focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-content flex-1 px-6 py-8">{children}</main>
        <footer className="border-t border-line bg-surface px-6 py-4 text-sm text-muted">
          <p>
            Historical data about past court outcomes. Not legal advice, and not a prediction of any
            future result.
          </p>
        </footer>
      </body>
    </html>
  );
}
