/**
 * demo-capture — scripted site-footage capture for the demo video.
 *
 * Records the video's site segments against the public production site as
 * read-only page loads: one browser, one context, sequential navigation,
 * human-scale pacing. Produces, per segment, a WebM master, an H.264 MP4
 * (ready for CapCut import), and high-resolution PNG stills of the blocks
 * the edit will punch in on.
 *
 * This is NOT a test. It lives outside the Playwright `testDir` (`tests/`),
 * matches no spec pattern, and never runs in CI.
 *
 * Invocation (from the repo root):
 *
 *   pnpm --filter @pca/e2e run capture -- \
 *     --segment <search-outcomes|sentencing-return|judge-view|all> \
 *     --out-dir <directory OUTSIDE the repo tree> \
 *     [--judge "<judge display name, required for judge-view/all>"] \
 *     [--base-url <origin, defaults to production; other values untested>]
 *
 * Everything the run produces lands under --out-dir; the repo working tree
 * is untouched. The script refuses an --out-dir inside the repo.
 *
 * TIMING CONSTANTS — the choreography's only tuning surface. Change values
 * here; nothing else needs editing. All values are milliseconds unless the
 * name says otherwise. Spec floors are noted where one exists; keep each
 * value at or above its floor.
 *
 *   TYPE_DELAY_MS          per-character delay for typed input
 *   PAGE_HOLD_MS           static hold at segment ends / page arrivals (floor 2s)
 *   DROPDOWN_HOLD_MS       hold with an autocomplete dropdown open in frame
 *   POST_ACTION_SETTLE_MS  beat between an action and the next movement
 *   OUTCOME_HOLD_MS        hold on the outcome group display (floor 8s)
 *   SENTENCING_HOLD_MS     hold on the sentencing detail block (floor 8s)
 *   CHARGE_TOP_HOLD_MS     sentencing-return opening hold at page top, outcome
 *                          mix in frame (floor 3s)
 *   RATES_HOLD_MS          hold on the sentencing rates block, explainer
 *                          string in frame (floor 4s)
 *   OUTCOME_MIX_HOLD_MS    return hold on the outcome mix (floor 4s)
 *   JUDGE_HOLD_MS          hold on the judge-specific result (floor 6s)
 *   SCROLL_DURATION_MS     duration of one eased scroll between blocks
 *   SCROLL_TOP_MARGIN_PX   gap left above a scrolled-to block, in CSS px
 *   SCROLL_MIN_TOP_MARGIN_PX  smallest top gap fit-aware framing may shrink to
 *   MOUSE_MOVE_DURATION_MS duration of one eased cursor glide
 *   MOUSE_STEP_MS          interval between cursor waypoints
 *   WAIT_TIMEOUT_MS        ceiling for page loads/element waits (cold loads
 *                          of the production site can exceed the default)
 *
 * Cursor: captures record the page compositor, never the OS cursor, so the
 * script injects its own overlay pointer (plus a click pulse) and drives it
 * with real mouse events. Playwright's screencast `showActions` cursor is
 * deliberately NOT used: it draws non-suppressible action-title text and
 * highlight boxes, which are barred from deliverable frames.
 *
 * Framing: the outcome-group-display and rates-block holds are fit-aware —
 * the top margin shrinks from SCROLL_TOP_MARGIN_PX toward
 * SCROLL_MIN_TOP_MARGIN_PX until the whole block fits the viewport. A block
 * that cannot fully fit even at the minimum margin is held top-anchored and
 * recorded as a FRAMING WARNING, reprinted in the end-of-run summary. Every
 * framing warning is a REPORT ITEM: it must appear verbatim in the
 * capture-run report and be adjudicated before the footage ships.
 */

import { execFile } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs, promisify } from 'node:util';
import ffmpegPath from 'ffmpeg-static';
import { chromium, type Locator, type Page } from '@playwright/test';

const execFileAsync = promisify(execFile);

// ---------------------------------------------------------------------------
// Timing constants (documented in the header; tune here only).
// ---------------------------------------------------------------------------

const TYPE_DELAY_MS = 120;
const PAGE_HOLD_MS = 2_600;
const DROPDOWN_HOLD_MS = 1_600;
const POST_ACTION_SETTLE_MS = 900;
const OUTCOME_HOLD_MS = 9_000;
const SENTENCING_HOLD_MS = 9_000;
const CHARGE_TOP_HOLD_MS = 3_400;
const RATES_HOLD_MS = 4_800;
const OUTCOME_MIX_HOLD_MS = 6_000;
const JUDGE_HOLD_MS = 7_000;
const SCROLL_DURATION_MS = 2_600;
const SCROLL_TOP_MARGIN_PX = 96;
const SCROLL_MIN_TOP_MARGIN_PX = 16;
const MOUSE_MOVE_DURATION_MS = 900;
const MOUSE_STEP_MS = 16;
const WAIT_TIMEOUT_MS = 60_000;

// ---------------------------------------------------------------------------
// Capture geometry. The edit canvas is 1080p; stills are taken from a
// deviceScaleFactor-2 context (screenshot scale 'device'), so element stills
// come out at twice their CSS size for clean punch-ins.
// ---------------------------------------------------------------------------

const VIEWPORT_WIDTH = 1920;
const VIEWPORT_HEIGHT = 1080;
const DEVICE_SCALE_FACTOR = 2;

// ---------------------------------------------------------------------------
// Targets. The charge is the demo charge by slug (a committed reference-data
// value, not corpus-derived); the judge is always a CLI argument.
// ---------------------------------------------------------------------------

const PROD_BASE_URL = 'https://philacourtoutcomes.org';
const CHARGE_SLUG = 'simple-assault';
const CHARGE_QUERY = 'simple assault';
const CHARGE_OPTION_NAME = 'Simple Assault';

const SELECTORS = {
  chargeSearchInput: '#charge-search',
  judgeFilterInput: '#judge-filter-input',
  outcomeSection: '[data-testid="section-outcome"]',
  sentencingSection: '[data-testid="section-sentencing"]',
  sentencingIndexSection: '[data-testid="section-sentencing-index"]',
  indexExplainer: '[data-testid="index-percentage-explainer"]',
  judgeFilterSection: '[data-testid="section-judge-filter"]',
  judgeOutcomeSection: '[data-testid="section-judge-outcome"]',
} as const;

const BUTTON_NAMES = {
  viewOutcomes: 'View outcomes',
  addJudgeFilter: 'Add judge filter',
} as const;

const SEGMENT_NAMES = ['search-outcomes', 'sentencing-return', 'judge-view'] as const;
type SegmentName = (typeof SEGMENT_NAMES)[number];

// ---------------------------------------------------------------------------
// Injected cursor overlay. The screencast records the page surface only, so
// a synthetic pointer (driven by the real mouse events below) is the cursor
// the viewer sees. mousedown adds a brief click pulse. pointer-events: none
// throughout — the overlay can never affect page behavior.
// ---------------------------------------------------------------------------

const CURSOR_INIT_SCRIPT = `(() => {
  if (window.top !== window) return;
  const CURSOR_ID = 'pca-capture-cursor';
  const ensureCursor = () => {
    if (!document.body) return null;
    let el = document.getElementById(CURSOR_ID);
    if (el) return el;
    el = document.createElement('div');
    el.id = CURSOR_ID;
    el.setAttribute('aria-hidden', 'true');
    el.style.cssText =
      'position:fixed;left:0;top:0;width:22px;height:30px;z-index:2147483647;' +
      'pointer-events:none;opacity:0;transition:opacity 150ms linear;';
    el.innerHTML =
      '<svg width="22" height="30" viewBox="0 0 22 30" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M1 1 L1 23 L7 18 L11 27 L15 25 L11 16 L19 16 Z" ' +
      'fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(el);
    return el;
  };
  window.addEventListener('mousemove', (e) => {
    const el = ensureCursor();
    if (!el) return;
    el.style.opacity = '1';
    el.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)';
  }, true);
  window.addEventListener('mousedown', (e) => {
    if (!document.body) return;
    const pulse = document.createElement('div');
    pulse.setAttribute('aria-hidden', 'true');
    pulse.style.cssText =
      'position:fixed;left:-17px;top:-17px;width:34px;height:34px;border-radius:50%;' +
      'border:2px solid rgba(30,64,175,0.75);z-index:2147483646;pointer-events:none;' +
      'opacity:0.9;transform:translate(' + e.clientX + 'px,' + e.clientY + 'px) scale(0.35);' +
      'transition:transform 320ms ease-out,opacity 320ms ease-out;';
    document.body.appendChild(pulse);
    requestAnimationFrame(() => {
      pulse.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px) scale(1)';
      pulse.style.opacity = '0';
    });
    setTimeout(() => pulse.remove(), 700);
  }, true);
  document.addEventListener('DOMContentLoaded', ensureCursor);
})();`;

// ---------------------------------------------------------------------------
// Cursor + scroll choreography helpers.
// ---------------------------------------------------------------------------

const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

/** Tracked on the Node side; mouse position survives navigations. */
let mousePosition = { x: Math.round(VIEWPORT_WIDTH / 2), y: Math.round(VIEWPORT_HEIGHT * 0.6) };

/** Glide the real mouse (and therefore the overlay cursor) along an eased path. */
async function glideTo(page: Page, targetX: number, targetY: number): Promise<void> {
  const steps = Math.max(2, Math.round(MOUSE_MOVE_DURATION_MS / MOUSE_STEP_MS));
  const from = { ...mousePosition };
  for (let i = 1; i <= steps; i++) {
    const eased = easeInOutCubic(i / steps);
    await page.mouse.move(from.x + (targetX - from.x) * eased, from.y + (targetY - from.y) * eased);
    await page.waitForTimeout(MOUSE_STEP_MS);
  }
  mousePosition = { x: targetX, y: targetY };
}

/** Glide to a locator's center and click it with real mouse events. */
async function glideClick(page: Page, target: Locator): Promise<void> {
  await target.waitFor({ state: 'visible' });
  const box = await target.boundingBox();
  if (!box) throw new Error('target for glideClick has no bounding box');
  await glideTo(page, box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.up();
}

/**
 * The overlay is per-document, so after a navigation the cursor is invisible
 * until the next mouse event; nudge the mouse to re-reveal it in place.
 */
async function revealCursor(page: Page): Promise<void> {
  await page.mouse.move(mousePosition.x + 1, mousePosition.y);
  await page.mouse.move(mousePosition.x, mousePosition.y);
}

/** Park the cursor at a neutral spot so it is in frame from the first frame. */
async function parkCursor(page: Page): Promise<void> {
  await page.mouse.move(mousePosition.x, mousePosition.y);
}

/** rAF-driven eased scroll placing the block `topMarginPx` from the top. */
async function easedScrollToBlock(
  page: Page,
  block: Locator,
  topMarginPx: number = SCROLL_TOP_MARGIN_PX,
): Promise<void> {
  await block.waitFor({ state: 'visible' });
  const targetY = await block.evaluate((el, margin) => {
    const rect = el.getBoundingClientRect();
    const maxY = document.documentElement.scrollHeight - window.innerHeight;
    return Math.max(0, Math.min(maxY, window.scrollY + rect.top - margin));
  }, topMarginPx);
  // No named inner functions here: tsx's keepNames transform would inject a
  // __name() helper that does not exist once the callback is serialized into
  // the page, so the rAF loop awaits promises instead of naming a callback.
  await page.evaluate(
    async ({ toY, duration }) => {
      const fromY = window.scrollY;
      const start = performance.now();
      for (;;) {
        const now = await new Promise<number>(requestAnimationFrame);
        const t = Math.min(1, (now - start) / duration);
        const eased = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
        window.scrollTo(0, fromY + (toY - fromY) * eased);
        if (t >= 1) return;
      }
    },
    { toY: targetY, duration: SCROLL_DURATION_MS },
  );
}

/**
 * Framing warnings surfaced at run end. Every entry is a REPORT ITEM: it must
 * appear verbatim in the capture-run report so framing is adjudicated before
 * the footage ships — a partially framed block must never ship silently.
 */
const framingWarnings: string[] = [];

/**
 * Fit-aware eased scroll: place the whole block in frame by shrinking the top
 * margin from SCROLL_TOP_MARGIN_PX toward SCROLL_MIN_TOP_MARGIN_PX when the
 * block is tall (block height varies with the served data shape; nothing here
 * assumes a row count). A block that cannot fully fit even at the minimum
 * margin is held top-anchored there and recorded as a framing warning.
 */
async function frameBlock(page: Page, block: Locator, label: string): Promise<void> {
  await block.waitFor({ state: 'visible' });
  const fit = await block.evaluate(
    (el, margins) => {
      const height = el.getBoundingClientRect().height;
      if (height <= window.innerHeight - margins.preferred) {
        return { marginPx: margins.preferred, clippedPx: 0 };
      }
      const shrunk = window.innerHeight - height;
      if (shrunk >= margins.minimum) return { marginPx: shrunk, clippedPx: 0 };
      return {
        marginPx: margins.minimum,
        clippedPx: Math.round(height + margins.minimum - window.innerHeight),
      };
    },
    { preferred: SCROLL_TOP_MARGIN_PX, minimum: SCROLL_MIN_TOP_MARGIN_PX },
  );
  if (fit.clippedPx > 0) {
    const warning =
      `FRAMING WARNING: ${label} does not fully fit the viewport even at the ` +
      `${SCROLL_MIN_TOP_MARGIN_PX}px minimum top margin (${fit.clippedPx}px clipped ` +
      'below the fold); held top-anchored — adjudicate before the footage ships';
    framingWarnings.push(warning);
    console.warn(`[capture] ${warning}`);
  }
  await easedScrollToBlock(page, block, fit.marginPx);
}

/** Scroll only when the block is not already fully inside the viewport. */
async function scrollToBlockIfNeeded(page: Page, block: Locator): Promise<void> {
  await block.waitFor({ state: 'visible' });
  const fullyInView = await block.evaluate((el) => {
    const rect = el.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= window.innerHeight;
  });
  if (!fullyInView) await easedScrollToBlock(page, block);
}

// ---------------------------------------------------------------------------
// Recording, stills, conversion.
// ---------------------------------------------------------------------------

async function withScreencast(
  page: Page,
  videoPath: string,
  run: () => Promise<void>,
): Promise<void> {
  await page.screencast.start({
    path: videoPath,
    size: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
  });
  await run();
  await page.screencast.stop();
}

function requireFfmpeg(): string {
  if (!ffmpegPath) throw new Error('ffmpeg-static provided no binary for this platform');
  return ffmpegPath;
}

/** Fail loudly if a recording did not come out at the exact capture size. */
async function assertVideoSize(videoPath: string): Promise<void> {
  const probe = await execFileAsync(requireFfmpeg(), ['-hide_banner', '-i', videoPath]).catch(
    // ffmpeg exits non-zero when no output is given; the stream info we need
    // is on stderr either way.
    (error: { stderr?: string }) => ({ stderr: error.stderr ?? '' }),
  );
  const expected = `${VIEWPORT_WIDTH}x${VIEWPORT_HEIGHT}`;
  if (!probe.stderr.includes(expected)) {
    throw new Error(`recording is not ${expected}: ${videoPath}`);
  }
}

async function convertToMp4(videoPath: string): Promise<string> {
  const mp4Path = videoPath.replace(/\.webm$/, '.mp4');
  await execFileAsync(requireFfmpeg(), [
    '-y',
    '-hide_banner',
    '-loglevel',
    'error',
    '-i',
    videoPath,
    '-c:v',
    'libx264',
    '-preset',
    'slow',
    '-crf',
    '16',
    '-pix_fmt',
    'yuv420p',
    '-movflags',
    '+faststart',
    mp4Path,
  ]);
  return mp4Path;
}

async function captureStill(block: Locator, stillPath: string): Promise<void> {
  // scale: 'device' is the documented default; explicit so the 2x contract
  // survives any future default change.
  await block.screenshot({ path: stillPath, scale: 'device' });
}

// ---------------------------------------------------------------------------
// Shared waits.
// ---------------------------------------------------------------------------

async function awaitChargeResult(page: Page): Promise<void> {
  await page.locator(SELECTORS.outcomeSection).waitFor({ state: 'visible' });
}

async function gotoChargePage(page: Page): Promise<void> {
  await page.goto(`/charges/${CHARGE_SLUG}`);
  await awaitChargeResult(page);
}

// ---------------------------------------------------------------------------
// Segments.
// ---------------------------------------------------------------------------

interface SegmentPaths {
  video: string;
  stillsDir: string;
}

/** Homepage → typed search with dropdown → charge page → outcome group display. */
async function segmentSearchOutcomes(page: Page, out: SegmentPaths): Promise<void> {
  await page.goto('/');
  const searchInput = page.locator(SELECTORS.chargeSearchInput);
  await searchInput.waitFor({ state: 'visible' });
  await parkCursor(page);

  await withScreencast(page, out.video, async () => {
    await page.waitForTimeout(PAGE_HOLD_MS);

    await glideClick(page, searchInput);
    await searchInput.pressSequentially(CHARGE_QUERY, { delay: TYPE_DELAY_MS });

    const option = page.getByRole('option', { name: CHARGE_OPTION_NAME }).first();
    await option.waitFor({ state: 'visible' });
    await page.waitForTimeout(DROPDOWN_HOLD_MS);
    await glideClick(page, option);
    await page.waitForTimeout(POST_ACTION_SETTLE_MS);

    await glideClick(page, page.getByRole('button', { name: BUTTON_NAMES.viewOutcomes }));
    await page.waitForURL(`**/charges/${CHARGE_SLUG}`);
    await awaitChargeResult(page);
    await revealCursor(page);
    await page.waitForTimeout(PAGE_HOLD_MS);

    await frameBlock(
      page,
      page.locator(SELECTORS.outcomeSection),
      'outcome group display (search-outcomes hold)',
    );
    await page.waitForTimeout(OUTCOME_HOLD_MS);
  });

  await captureStill(
    page.locator(SELECTORS.outcomeSection),
    path.join(out.stillsDir, 'outcome-distribution.png'),
  );
}

/**
 * Charge page at top (outcome mix in frame) → sentencing detail block
 * (conditional caption in frame, live-read hold) → sentencing rates block
 * (explainer string in frame) → return to the outcome mix (closer footage).
 */
async function segmentSentencingReturn(page: Page, out: SegmentPaths): Promise<void> {
  await gotoChargePage(page);
  const sentencing = page.locator(SELECTORS.sentencingSection);
  if ((await sentencing.count()) === 0) {
    throw new Error(
      'sentencing block not present on the charge page — the published data shape ' +
        'has changed; re-check the segment plan before re-shooting',
    );
  }
  const ratesBlock = page.locator(SELECTORS.sentencingIndexSection);
  const explainer = page.locator(SELECTORS.indexExplainer);
  if ((await ratesBlock.count()) === 0 || (await explainer.count()) === 0) {
    throw new Error(
      'sentencing rates block or its explainer string is not present on the charge ' +
        'page — the published data shape has changed (zero-sentenced or index-absent ' +
        'arm); re-check the segment plan before re-shooting',
    );
  }
  await parkCursor(page);

  await withScreencast(page, out.video, async () => {
    // Beat 1: literal page-top hold — the outcome mix sits near the top of the
    // page, so there is no opening scroll; full-display framing belongs to the
    // Beat 4 return.
    await page.waitForTimeout(CHARGE_TOP_HOLD_MS);

    // Beat 2: sentencing detail, top-aligned so the conditional caption is
    // fully in frame; live-read hold.
    await easedScrollToBlock(page, sentencing);
    await page.waitForTimeout(SENTENCING_HOLD_MS);

    // Beat 3: rates block, explainer string guaranteed in frame (the explainer
    // sits at the block's trailing edge; the extra scroll no-ops when the
    // fit-aware framing already shows it).
    await frameBlock(page, ratesBlock, 'sentencing rates block (sentencing-return hold)');
    await scrollToBlockIfNeeded(page, explainer);
    await page.waitForTimeout(RATES_HOLD_MS);

    // Beat 4: slow scroll back up to the outcome mix — the closer footage,
    // full grouped display framed.
    await frameBlock(
      page,
      page.locator(SELECTORS.outcomeSection),
      'outcome group display (sentencing-return closer)',
    );
    await page.waitForTimeout(OUTCOME_MIX_HOLD_MS);
  });

  await captureStill(sentencing, path.join(out.stillsDir, 'sentencing-block.png'));
  await captureStill(ratesBlock, path.join(out.stillsDir, 'sentencing-rates.png'));
  await captureStill(
    page.locator(SELECTORS.outcomeSection),
    path.join(out.stillsDir, 'outcome-mix.png'),
  );
}

/** Charge page → open judge filter → typed judge search → judge-specific result. */
async function segmentJudgeView(page: Page, out: SegmentPaths, judgeName: string): Promise<void> {
  await gotoChargePage(page);
  await parkCursor(page);

  await withScreencast(page, out.video, async () => {
    await page.waitForTimeout(PAGE_HOLD_MS);

    const disclosure = page.getByRole('button', { name: BUTTON_NAMES.addJudgeFilter });
    await scrollToBlockIfNeeded(page, disclosure);
    await glideClick(page, disclosure);
    await page.locator(SELECTORS.judgeFilterSection).waitFor({ state: 'visible' });
    await page.waitForTimeout(POST_ACTION_SETTLE_MS);

    const judgeInput = page.locator(SELECTORS.judgeFilterInput);
    await glideClick(page, judgeInput);
    await judgeInput.pressSequentially(judgeName, { delay: TYPE_DELAY_MS });

    const option = page.getByRole('option', { name: judgeName }).first();
    await option.waitFor({ state: 'visible' });
    await page.waitForTimeout(DROPDOWN_HOLD_MS);
    await glideClick(page, option);

    await page.waitForURL(`**/charges/${CHARGE_SLUG}/judge/**`);
    // The judge autocomplete does not filter by availability for this charge;
    // if the page renders the no-data notice instead of a judge-specific
    // result, fail with an actionable message rather than a bare timeout.
    const judgeOutcome = page.locator(SELECTORS.judgeOutcomeSection);
    const noDataNotice = page.getByText('No judge-specific aggregate');
    await judgeOutcome.or(noDataNotice).first().waitFor({ state: 'visible' });
    if (await noDataNotice.count()) {
      throw new Error(
        `no judge-specific result is published for this charge and "${judgeName}" — ` +
          'pick a judge with available results and re-run',
      );
    }
    await revealCursor(page);
    await page.waitForTimeout(POST_ACTION_SETTLE_MS);

    await scrollToBlockIfNeeded(page, judgeOutcome);
    await page.waitForTimeout(JUDGE_HOLD_MS);
  });

  await captureStill(
    page.locator(SELECTORS.judgeOutcomeSection),
    path.join(out.stillsDir, 'judge-result.png'),
  );
}

// ---------------------------------------------------------------------------
// CLI.
// ---------------------------------------------------------------------------

const USAGE = `Usage:
  pnpm --filter @pca/e2e run capture -- --segment <name> --out-dir <dir> [--judge "<name>"] [--base-url <origin>]

  --segment   ${SEGMENT_NAMES.join(' | ')} | all
  --out-dir   output directory OUTSIDE the repo tree (created if missing)
  --judge     judge display name; required for judge-view and all
  --base-url  target origin (default: production; non-default values are untested)`;

function fail(message: string): never {
  console.error(`[capture] ${message}\n\n${USAGE}`);
  process.exit(1);
}

function expandHome(p: string): string {
  return p === '~' || p.startsWith('~/') ? path.join(os.homedir(), p.slice(1)) : p;
}

async function main(): Promise<void> {
  // pnpm forwards the conventional `--` separator into argv; drop it so both
  // `run capture -- --segment ...` and `run capture --segment ...` work.
  const args = process.argv.slice(2);
  if (args[0] === '--') args.shift();
  const { values } = parseArgs({
    args,
    options: {
      segment: { type: 'string' },
      judge: { type: 'string' },
      'out-dir': { type: 'string' },
      'base-url': { type: 'string' },
    },
  });

  const segmentArg = values.segment ?? fail('--segment is required');
  const outDirArg = values['out-dir'] ?? fail('--out-dir is required');

  const segments: SegmentName[] =
    segmentArg === 'all'
      ? [...SEGMENT_NAMES]
      : SEGMENT_NAMES.includes(segmentArg as SegmentName)
        ? [segmentArg as SegmentName]
        : fail(`unknown segment "${segmentArg}"`);

  const judgeName = values.judge;
  if (segments.includes('judge-view') && !judgeName) {
    fail('--judge is required for the judge-view segment');
  }

  const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
  const outDir = path.resolve(process.cwd(), expandHome(outDirArg));
  if (outDir === repoRoot || outDir.startsWith(repoRoot + path.sep)) {
    fail('--out-dir must be OUTSIDE the repository tree; nothing generated is committed');
  }

  const baseURL = values['base-url'] ?? PROD_BASE_URL;
  if (baseURL !== PROD_BASE_URL) {
    console.warn(`[capture] non-default base URL ${baseURL} — this mode is untested`);
  }

  const stillsDir = path.join(outDir, 'stills');
  await mkdir(stillsDir, { recursive: true });
  requireFfmpeg();

  console.log(`[capture] output directory: ${outDir}`);
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      baseURL,
      viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
      deviceScaleFactor: DEVICE_SCALE_FACTOR,
      colorScheme: 'light',
      locale: 'en-US',
      timezoneId: 'America/New_York',
    });
    context.setDefaultTimeout(WAIT_TIMEOUT_MS);
    context.setDefaultNavigationTimeout(WAIT_TIMEOUT_MS);
    await context.addInitScript(CURSOR_INIT_SCRIPT);
    const page = await context.newPage();

    for (const segment of segments) {
      const out: SegmentPaths = { video: path.join(outDir, `${segment}.webm`), stillsDir };
      console.log(`[capture] recording segment: ${segment}`);
      if (segment === 'search-outcomes') await segmentSearchOutcomes(page, out);
      else if (segment === 'sentencing-return') await segmentSentencingReturn(page, out);
      else await segmentJudgeView(page, out, judgeName as string);

      await assertVideoSize(out.video);
      const mp4Path = await convertToMp4(out.video);
      console.log(`[capture] wrote ${out.video}`);
      console.log(`[capture] wrote ${mp4Path}`);
    }
    if (framingWarnings.length > 0) {
      // Reprinted so the run summary carries every warning verbatim into the
      // capture-run report; a partially framed hold never ships silently.
      console.warn('[capture] framing warnings (report items; adjudicate before the edit):');
      for (const warning of framingWarnings) console.warn(`[capture]   ${warning}`);
    } else {
      console.log('[capture] framing: all holds fully framed');
    }
    console.log(`[capture] stills in ${stillsDir}`);
    console.log('[capture] done');
  } finally {
    await browser.close();
  }
}

void main().catch((error: unknown) => {
  console.error('[capture] failed:', error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
