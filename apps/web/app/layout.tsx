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
        <header className="site-header">
          <p className="site-name">Philadelphia Court Outcomes</p>
          <nav aria-label="Main navigation">
            <ul className="site-nav">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href}>{link.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
        </header>
        <main className="site-main">{children}</main>
        <footer className="site-footer">
          <p>
            Historical data about past court outcomes. Not legal advice, and not a prediction of any
            future result.
          </p>
        </footer>
      </body>
    </html>
  );
}
