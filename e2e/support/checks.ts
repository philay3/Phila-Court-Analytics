import AxeBuilder from '@axe-core/playwright';
import { expect, type Page } from '@playwright/test';
import { scanPublicCopy } from '@pca/shared';
import { formatViolations, scanForForbidden } from '@pca/shared/forbidden-scan';

/**
 * The universal per-page gate (task 15.2 scope 3–5). EVERY page/state the suite
 * visits — including every unavailable/not-found state and the 390px mobile
 * pass — is run through this once it has rendered:
 *
 *   1. axe-core at WCAG 2.2 AA (the five tag families below) — zero violations.
 *   2. scanPublicCopy over the rendered visible text — zero copy-safety
 *      violations. This is the SAME checker the web copy-guard runs over copy
 *      modules; here it re-scans the fully composed page (chrome + API-served
 *      content) as actually rendered.
 *   3. scanForForbidden over the rendered visible text — zero privacy
 *      violations. The relocated 10.1 checker (imported from
 *      @pca/shared/forbidden-scan) is reused verbatim. On a rendered page the
 *      meaningful surface is text VALUES (docket-number / defendant-identifier
 *      shapes), so the page's innerText is fed as the scanned string; the
 *      checker's key-stem arm is inert on plain text by construction.
 *
 * No term or field list is defined or duplicated here — all three checkers own
 * their lists inside @pca/shared. A single call site keeps coverage honest:
 * forgetting the gate on a new page is a visible omission in the spec.
 */
const WCAG_AA_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

export async function assertPageClean(page: Page, label: string): Promise<void> {
  // On a client-side (SPA) navigation Next updates document.title a tick after
  // the content paints; scanning before it settles trips axe's document-title
  // rule on a transient empty title. Every route resolves a non-empty title
  // (route metadata or the layout default template), so wait for that first.
  await expect(page, `[${label}] document title never became non-empty`).toHaveTitle(/.+/);

  const axe = await new AxeBuilder({ page }).withTags(WCAG_AA_TAGS).analyze();
  expect(
    axe.violations,
    `[${label}] axe WCAG 2.2 AA violations:\n${JSON.stringify(
      axe.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })),
      null,
      2,
    )}`,
  ).toEqual([]);

  const text = await page.locator('body').innerText();

  const copyViolations = scanPublicCopy(text);
  expect(
    copyViolations,
    `[${label}] rendered-copy safety violations:\n${JSON.stringify(copyViolations, null, 2)}`,
  ).toEqual([]);

  const forbidden = scanForForbidden(text);
  expect(
    forbidden,
    `[${label}] rendered-page privacy violations:\n${formatViolations(forbidden)}`,
  ).toEqual([]);
}
