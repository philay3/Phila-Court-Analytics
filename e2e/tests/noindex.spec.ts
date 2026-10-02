import { expect, test } from '@playwright/test';
import { SLUGS } from '../support/constants';

/**
 * Static-serving contract (task STATIC-2b, pins 8 and 14). The site-wide
 * noindex is carried BOTH in the document (`<meta name="robots">`, from the
 * root layout metadata) and on the wire (`X-Robots-Tag` from `_headers`,
 * which Cloudflare Pages applies to every path — data files and the 404
 * included). The export's canonical URLs carry no trailing slash
 * (`trailingSlash: false`), so a page URL is served directly, never redirected.
 */

const ROBOTS = 'noindex, nofollow';

test('every served path carries X-Robots-Tag; pages also carry the robots meta', async ({
  page,
}) => {
  for (const path of ['/', `/charges/${SLUGS.chargeDataBearing}`, '/methodology']) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(200);
    expect(response?.headers()['x-robots-tag'], path).toBe(ROBOTS);
    await expect(page.locator('meta[name="robots"]'), path).toHaveAttribute('content', ROBOTS);
  }

  const data = await page.request.get('/data/search-index.json');
  expect(data.status()).toBe(200);
  expect(data.headers()['x-robots-tag']).toBe(ROBOTS);

  const notFound = await page.request.get('/no-such-path');
  expect(notFound.status()).toBe(404);
  expect(notFound.headers()['x-robots-tag']).toBe(ROBOTS);
});

test('page URLs are served without a trailing-slash redirect', async ({ page }) => {
  const response = await page.request.get('/methodology', { maxRedirects: 0 });
  expect(response.status()).toBe(200);
  expect(response.url()).toMatch(/\/methodology$/);
});
