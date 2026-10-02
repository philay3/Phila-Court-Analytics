import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';

/*
 * Operator dashboard shell (task STATIC-2a). Local only, never deployed:
 * noindex is set for hygiene, not because the app is ever reachable. The
 * theme is the web app's globals.css copied verbatim so the relocated
 * dashboard's tokens (ink/paper/band/cat-N fills) resolve; the self-hosted
 * Google fonts are deliberately not wired here, so the serif/sans variables
 * fall back to the stacks declared in the @theme block.
 */
export const metadata: Metadata = {
  title: {
    default: 'PCA Operations',
    template: '%s — PCA Operations',
  },
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main className="mx-auto w-full max-w-shell px-4 pt-8 pb-12">{children}</main>
      </body>
    </html>
  );
}
