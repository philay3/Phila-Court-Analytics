/**
 * readme-screenshots — reproducible capture of the README's screenshot set
 * (task README-1, crops revised in the post-report review pass).
 *
 * Loads the public pages of the production site as read-only, sequential
 * navigations (ordinary visitor traffic — no interaction beyond navigation
 * and framing scrolls) and writes the PNGs the root README embeds, at
 * stable committed paths under docs/images/. Rerunning the script
 * regenerates the same shot set at the same paths.
 *
 * Crop philosophy (review ruling): the homepage hero is the only full-width,
 * page-scale shot. Every other image is a tight, column-clipped crop of one
 * block, so each screenshot shows exactly the section the surrounding README
 * prose is explaining.
 *
 * This is NOT a test. Like demo-capture.ts it lives outside the Playwright
 * `testDir` (`tests/`), matches no spec pattern, and never runs in CI.
 *
 * Invocation (from the repo root):
 *
 *   pnpm --filter @pca/e2e run capture:readme
 *
 * Fixed capture parameters (pinned by the task; not a tuning surface):
 *
 *   VIEWPORT      1440x900, deviceScaleFactor 1, headless, no browser chrome
 *   MAX_PNG_BYTES 300 KB per image — the script fails loudly if any capture
 *                 exceeds it rather than compressing or resizing
 *
 * Judge-axis content is excluded from every image by construction: no shot
 * navigates to a judge page, opens the judge filter, or scrolls a
 * judge-specific block into frame.
 */

import { mkdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, type Page } from '@playwright/test';

const BASE_URL = 'https://philacourtoutcomes.org';
const VIEWPORT = { width: 1440, height: 900 };
const MAX_PNG_BYTES = 300 * 1024;
const WAIT_TIMEOUT_MS = 45_000;
/** Breathing room, in CSS px, around element-anchored crops. */
const CROP_MARGIN_PX = 24;

const OUT_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  'docs',
  'images',
);

interface Shot {
  /** Output filename under docs/images/. */
  file: string;
  /** Page path on the production site. */
  pagePath: string;
  /** Selector that must be visible before capture (readiness gate). */
  readySelector: string;
  /**
   * Crop strategy: 'top-through' clips full-width from the page top down
   * through the bottom of `cropSelector` (hero use only); 'element' clips
   * tightly to `cropSelector`'s bounding box; 'range' clips from the top of
   * `cropSelector` through the bottom of `cropEndSelector`. 'element' and
   * 'range' clip horizontally to the blocks' own column, not the viewport.
   */
  crop: 'top-through' | 'element' | 'range';
  cropSelector: string;
  cropEndSelector?: string;
}

const SHOTS: readonly Shot[] = [
  // Hero — the only full-width, page-scale shot (review ruling).
  {
    file: 'readme-home.png',
    pagePath: '/',
    readySelector: 'section[aria-labelledby="featured-charges-heading"]',
    crop: 'top-through',
    cropSelector: 'section[aria-labelledby="featured-charges-heading"]',
  },
  // Directory — heading, filter box, and the top of the charge list, column
  // only (starting at the H1 keeps the site nav out of frame).
  {
    file: 'readme-charges.png',
    pagePath: '/charges',
    readySelector: 'main h1',
    crop: 'range',
    cropSelector: 'main h1',
    cropEndSelector: 'main',
  },
  // Simple-assault worked example, one tight crop per block the README prose
  // explains, in the canonical page order (prerecord-2 ruling 1): page top,
  // outcome distribution, sentencing detail, sentencing rates.
  {
    file: 'readme-result-top.png',
    pagePath: '/charges/simple-assault',
    readySelector: '[data-testid="section-summary"]',
    crop: 'range',
    cropSelector: '[data-testid="section-summary"]',
    cropEndSelector: '[data-testid="section-responsible-use"]',
  },
  {
    file: 'readme-result-outcomes.png',
    pagePath: '/charges/simple-assault',
    readySelector: '[data-testid="section-outcome"]',
    crop: 'element',
    cropSelector: '[data-testid="section-outcome"]',
  },
  {
    file: 'readme-result-sentencing.png',
    pagePath: '/charges/simple-assault',
    readySelector: '[data-testid="section-sentencing"]',
    crop: 'element',
    cropSelector: '[data-testid="section-sentencing"]',
  },
  {
    file: 'readme-result-rates.png',
    pagePath: '/charges/simple-assault',
    readySelector: '[data-testid="section-sentencing-index"]',
    crop: 'element',
    cropSelector: '[data-testid="section-sentencing-index"]',
  },
];

const CHARGES_LIST_MAX_HEIGHT_PX = 860;

async function clipFor(
  page: Page,
  shot: Shot,
): Promise<{ x: number; y: number; width: number; height: number }> {
  const box = await page.locator(shot.cropSelector).boundingBox();
  if (box === null) {
    throw new Error(`shot ${shot.file}: ${shot.cropSelector} has no bounding box`);
  }
  if (shot.crop === 'top-through') {
    return {
      x: 0,
      y: 0,
      width: VIEWPORT.width,
      height: Math.ceil(box.y + box.height + CROP_MARGIN_PX),
    };
  }
  const endBox =
    shot.crop === 'range' && shot.cropEndSelector !== undefined
      ? await page.locator(shot.cropEndSelector).boundingBox()
      : box;
  if (endBox === null) {
    throw new Error(`shot ${shot.file}: ${shot.cropEndSelector} has no bounding box`);
  }
  const x = Math.max(0, Math.floor(Math.min(box.x, endBox.x) - CROP_MARGIN_PX));
  const right = Math.min(
    VIEWPORT.width,
    Math.ceil(Math.max(box.x + box.width, endBox.x + endBox.width) + CROP_MARGIN_PX),
  );
  const top = Math.max(0, Math.floor(box.y - CROP_MARGIN_PX));
  let height = Math.ceil(endBox.y + endBox.height + CROP_MARGIN_PX - top);
  // The charge directory is a long list; a tight-but-bounded crop of its top
  // is the shot, not the whole list.
  if (shot.file === 'readme-charges.png') {
    height = Math.min(height, CHARGES_LIST_MAX_HEIGHT_PX);
  }
  return { x, y: top, width: right - x, height };
}

async function main(): Promise<void> {
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.setDefaultTimeout(WAIT_TIMEOUT_MS);

  const oversized: string[] = [];
  for (const shot of SHOTS) {
    const url = `${BASE_URL}${shot.pagePath}`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: WAIT_TIMEOUT_MS });
    await page.locator(shot.readySelector).first().waitFor({ state: 'visible' });

    const clip = await clipFor(page, shot);
    const outPath = path.join(OUT_DIR, shot.file);
    await page.screenshot({ path: outPath, clip, fullPage: true });

    const { size } = await stat(outPath);
    const sizeKb = Math.round(size / 1024);
    const flag = size > MAX_PNG_BYTES ? '  ** OVER 300 KB CAP **' : '';
    if (size > MAX_PNG_BYTES) oversized.push(shot.file);
    console.log(`${shot.file}  ${clip.width}x${clip.height}  ${sizeKb} KB  (${url})${flag}`);
  }

  await browser.close();

  if (oversized.length > 0) {
    console.error(
      `FAILED size cap: ${oversized.join(', ')} exceed ${MAX_PNG_BYTES / 1024} KB — stop and report; do not compress or resize without adjudication.`,
    );
    process.exitCode = 1;
    return;
  }
  console.log(`Done: ${SHOTS.length} screenshots written to ${OUT_DIR}`);
}

await main();
