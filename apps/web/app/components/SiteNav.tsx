'use client';

/**
 * Masthead nav (task DP-2, pinned decision A5; DP-4 lands the third item):
 * exactly Home · Charges · Methodology. The Definitions / Data Coverage /
 * About labels relocated to the footer link row in layout.tsx — all five
 * label strings and hrefs are the pre-restyle values, byte-identical (A5
 * relocation, not rewording).
 *
 * Client component only for the active-tab state (Civic Atlas: active item
 * bold with a 2px ink underline); `usePathname` needs the client runtime.
 * Exact-match is correct for every entry: /charges highlights only the
 * directory itself; result routes highlight nothing.
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_LINKS = [
  { href: '/', label: 'Home' },
  { href: '/charges', label: 'Charges' },
  { href: '/methodology', label: 'Methodology' },
] as const;

export function SiteNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main navigation" className="border-b border-hairline">
      <ul className="flex flex-wrap justify-center gap-x-2">
        {NAV_LINKS.map((link) => {
          const active = pathname === link.href;
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={active ? 'page' : undefined}
                className={`inline-block px-4 py-3 text-sm text-ink hover:text-accent ${
                  active ? 'border-b-2 border-ink font-bold' : ''
                }`}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
