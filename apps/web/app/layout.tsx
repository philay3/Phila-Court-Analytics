import type { Metadata } from 'next';
import Link from 'next/link';
import { Source_Serif_4, Source_Sans_3 } from 'next/font/google';
import type { ReactNode } from 'react';
import { SiteNav } from './components/SiteNav';
import './globals.css';

/*
 * Civic Atlas families (task DP-2, pinned decision A4): next/font/google
 * self-hosts both at build time — the built output serves the font files
 * from _next/static and makes no runtime request to Google domains. Both
 * are variable fonts, so no weight list is needed. The CSS variables are
 * consumed by @theme in globals.css (--font-serif / --font-sans).
 */
const sourceSerif = Source_Serif_4({
  subsets: ['latin'],
  style: ['normal', 'italic'],
  variable: '--font-source-serif-4',
});
const sourceSans = Source_Sans_3({
  subsets: ['latin'],
  variable: '--font-source-sans-3',
});

export const metadata: Metadata = {
  // Brand per the DP-2 plan-approval amendment (Chops, 2026-07-18): the site
  // brand is 'Phila Court Outcomes' — the one sanctioned copy change of DP-2.
  // Exactly three surfaces carry it: this title pair, the masthead brand,
  // and the footer lockup. All other self-references stay frozen.
  title: {
    default: 'Phila Court Outcomes',
    template: '%s — Phila Court Outcomes',
  },
  description: 'Historical aggregate outcomes in Philadelphia criminal court cases.',
  // Deliberate site-wide noindex: per the front-end spec, indexing is opt-in
  // after review. Revisit at launch readiness.
  robots: {
    index: false,
    follow: false,
  },
};

/*
 * Footer link row (pinned decision A5): exactly About · Definitions ·
 * Data Coverage. These three labels and hrefs relocated verbatim from the
 * pre-restyle nav; Home and Methodology live in <SiteNav>.
 */
const FOOTER_LINKS = [
  { href: '/about', label: 'About' },
  { href: '/definitions', label: 'Definitions' },
  { href: '/data-coverage', label: 'Data Coverage' },
] as const;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${sourceSerif.variable} ${sourceSans.variable}`}>
      <body>
        <header className="border-t border-ink bg-paper">
          {/* Masthead lockup between the 1px top rule and the 3px double rule;
              CSS-uppercased — the source brand string stays title case. */}
          <div className="border-b-3 border-double border-ink px-6 py-5 text-center">
            <p className="font-serif text-xl font-semibold tracking-[.14em] text-ink uppercase tablet:text-2xl">
              Phila Court Outcomes
            </p>
          </div>
          <SiteNav />
        </header>
        {/* 1200px app shell (DP-3): gutters 16/24/28/32px and page top/bottom
            padding 32-56/48-80px step by tier per bglad §5.2/§5.3. Routes
            constrain themselves inside it (article pages via max-w-article,
            result pages via the two-column grid). */}
        <main className="mx-auto w-full max-w-shell flex-1 px-4 pt-8 pb-12 tablet:px-6 tablet:pt-11 tablet:pb-16 desktop:px-7 desktop:pt-14 desktop:pb-20 wide:px-8">
          {children}
        </main>
        <footer className="border-t-3 border-double border-ink bg-band px-6 py-6 text-sm">
          <div className="mx-auto flex w-full max-w-shell flex-col gap-3 tablet:flex-row tablet:items-baseline tablet:justify-between">
            <p className="font-serif font-semibold tracking-[.14em] text-ink uppercase">
              Phila Court Outcomes
            </p>
            <ul className="flex flex-wrap gap-x-5">
              {FOOTER_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="inline-block py-3 text-accent hover:text-accent-hover hover:underline tablet:py-1"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <p className="mx-auto mt-2 w-full max-w-shell text-muted">
            Historical data about past court outcomes. Not legal advice, and not a prediction of any
            future result.
          </p>
        </footer>
      </body>
    </html>
  );
}
