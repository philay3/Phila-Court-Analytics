import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import {
  AGGREGATE_RUN_LABEL_PREFIX,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  ERROR_BOUNDARY_COPY,
  FETCH_FAILURE_MESSAGE,
  PUBLIC_ERROR_MESSAGES,
  ROOT_NOT_FOUND_HEADING,
  ROOT_NOT_FOUND_MESSAGE,
} from '@pca/shared';
import {
  BAKED_STATE_STRINGS,
  LEGACY_JUDGE_REDIRECT,
  hasNoindexMeta,
  headersHaveNoindexRule,
  payloadStrings,
  redirectsHaveLegacyJudgeRule,
  runExportGate,
  visibleText,
  type GateResult,
} from './gate.js';
import type { ExportManifest } from './manifest.js';

/**
 * Fixture export built from INVENTED content (alpha charge, a fictional judge,
 * made-up run ids) in a temp directory, in the shape the real export has
 * (plan §1.3). Every failure class of pin 3.A.9 is proven to fire on a
 * mutation of the clean fixture, and the clean fixture passes.
 */

const RUN = '0f1e2d3c-0000-4000-8000-00000000c0de';
const OTHER_RUN = 'ffffffff-0000-4000-8000-000000000bad';
const ROBOTS = '<meta name="robots" content="noindex, nofollow"/>';
// The synthetic docket SHAPE the shared forbidden-fields tests already use; not a real docket.
const SYNTHETIC_DOCKET_SHAPE = 'CP-51-CR-0001234-2025';

function page(title: string, body: string, options: { robots?: boolean } = {}): string {
  const robots = options.robots === false ? '' : ROBOTS;
  // The not-found copy inside a script and a forbidden word inside a style
  // prove that neither counts as visible text.
  return (
    `<!DOCTYPE html><html><head>${robots}<title>${title}</title>` +
    `<style>.odds{display:none}</style>` +
    `<script>self.__next_f.push([1,"${ROOT_NOT_FOUND_HEADING}"])</script></head>` +
    `<body><main><h1>${title}</h1>${body}</main></body></html>`
  );
}

function rsc(text: string): string {
  return `1:"$Sreact.fragment"\n2:["$","main",null,{"children":${JSON.stringify(text)}}]\n`;
}

const CLEAN_FILES: Record<string, string> = {
  'index.html': page('Search', '<p>Search court outcomes by charge.</p>'),
  'about.html': page('About this site', '<p>About this site &amp; its data.</p>'),
  'charges.html': page('Charges', '<ul><li>Alpha Charge</li></ul>'),
  'charges/alpha-charge.html': page(
    'Alpha Charge',
    `<p>Outcome mix.</p><p>${AGGREGATE_RUN_LABEL_PREFIX}${RUN.slice(0, 8)}</p>`,
  ),
  '404.html': page(ROOT_NOT_FOUND_HEADING, `<p>${ROOT_NOT_FOUND_MESSAGE}</p>`),
  '_not-found.html': page(ROOT_NOT_FOUND_HEADING, `<p>${ROOT_NOT_FOUND_MESSAGE}</p>`),
  'index.txt': rsc('Search'),
  'about.txt': rsc('About this site'),
  'charges.txt': rsc('Charges'),
  'charges/alpha-charge.txt': rsc('Alpha Charge'),
  '_not-found.txt': rsc(ROOT_NOT_FOUND_HEADING),
  '__next._tree.txt': rsc('tree'),
  'about/__next._tree.txt': rsc('tree'),
  'about/__next.about.__PAGE__.txt': rsc('About this site'),
  'charges/__next._tree.txt': rsc('tree'),
  'charges/alpha-charge/__next.charges.$d$chargeSlug.__PAGE__.txt': rsc('Alpha Charge'),
  '_not-found/__next._tree.txt': rsc('tree'),
  'data/search-index.json': JSON.stringify({
    available: true,
    aggregateRunId: RUN,
    taxonomyVersion: '1.0.0',
    lastRefreshed: '2026-01-01T00:00:00.000Z',
    charges: [{ slug: 'alpha-charge', displayName: 'Alpha Charge', aliases: ['alpha'] }],
    judges: [
      { slug: 'judge-fictional-example', displayName: 'Judge Fictional Example', aliases: [] },
    ],
    pairs: [{ chargeSlug: 'alpha-charge', judgeSlug: 'judge-fictional-example' }],
  }),
  'data/charges/alpha-charge.json': JSON.stringify({
    aggregateRunId: RUN,
    chargeSlug: 'alpha-charge',
    judges: {},
  }),
  _headers: '/*\n  X-Robots-Tag: noindex, nofollow\n',
  _redirects: `${LEGACY_JUDGE_REDIRECT}\n`,
  '_next/static/chunks/app.js': 'console.log("app");\n',
  'favicon.ico': 'ico-bytes',
  'icon.svg': '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
};

function cleanManifest(): ExportManifest {
  return {
    version: 1,
    mode: 'ci',
    aggregateRunId: RUN,
    generatedAt: '2026-01-01T00:00:00.000Z',
    routes: ['/', '/about', '/charges', '/charges/alpha-charge'],
    notFound: ['404.html', '_not-found.html'],
    dataFiles: ['data/search-index.json', 'data/charges/alpha-charge.json'],
    assets: ['_headers', '_redirects', '_next/static/chunks/app.js', 'favicon.ico', 'icon.svg'],
  };
}

const dirs: string[] = [];
afterEach(() => {
  for (const dir of dirs.splice(0)) {
    rmSync(dir, { recursive: true, force: true });
  }
});

/** Writes the clean fixture with `overrides` applied (a `null` value omits the file). */
function fixture(overrides: Record<string, string | null> = {}): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'pca-gate-'));
  dirs.push(dir);
  const files = { ...CLEAN_FILES, ...overrides };
  for (const [rel, content] of Object.entries(files)) {
    if (content === null) continue;
    const full = path.join(dir, rel);
    mkdirSync(path.dirname(full), { recursive: true });
    writeFileSync(full, content);
  }
  return dir;
}

function gate(
  exportDir: string,
  manifest: ExportManifest = cleanManifest(),
  limits?: { maxFiles?: number; maxFileBytes?: number },
): GateResult {
  return runExportGate({ exportDir, manifest, limits });
}

function expectViolation(result: GateResult, ...fragments: string[]): void {
  expect(result.ok).toBe(false);
  for (const fragment of fragments) {
    expect(
      result.violations.some((v) => v.includes(fragment)),
      `expected a violation containing "${fragment}"; got:\n${result.violations.join('\n')}`,
    ).toBe(true);
  }
}

describe('export gate — clean fixture', () => {
  it('passes and reports the measured summary', () => {
    const result = gate(fixture());
    expect(result.violations).toEqual([]);
    expect(result.ok).toBe(true);
    expect(result.summary.walked).toEqual({ html: 6, payload: 11, data: 2, asset: 5 });
    expect(result.summary.totalFiles).toBe(24);
    expect(result.summary.pagesChecked).toBe(6);
    expect(result.summary.pagesUnderBakedStateRule).toBe(4);
    expect(result.summary.dataFilesChecked).toBe(2);
    expect(result.summary.aggregateRunId).toBe(RUN);
    expect(result.summary.largestFile.bytes).toBeGreaterThan(0);
    expect(result.summary.limits).toEqual({ maxFiles: 15_000, maxFileBytes: 20 * 1024 * 1024 });
  });

  it('exempts the two not-found pages from the baked-state rule and ignores script/style content', () => {
    // The clean fixture carries the root 404 copy in every page's <script>
    // and the word "odds" in every page's <style>: neither is visible text.
    expect(gate(fixture()).ok).toBe(true);
  });
});

describe('forbidden content (scanners from @pca/shared)', () => {
  it('fires on a forbidden field in a data file', () => {
    const dir = fixture({
      'data/charges/alpha-charge.json': JSON.stringify({
        aggregateRunId: RUN,
        chargeSlug: 'alpha-charge',
        judges: {},
        docketNumber: 'redacted',
      }),
    });
    expectViolation(gate(dir), 'data/charges/alpha-charge.json', 'forbidden key "docketNumber"');
  });

  it('fires on a forbidden value shape in a page, even inside the raw flight data', () => {
    const dir = fixture({
      'about.html': page('About', `<p>filed</p><script>["${SYNTHETIC_DOCKET_SHAPE}"]</script>`),
    });
    const result = gate(dir);
    expectViolation(result, 'about.html', 'forbidden value shape');
    // The offending value itself is never echoed.
    expect(result.violations.join('\n')).not.toContain(SYNTHETIC_DOCKET_SHAPE);
  });

  it('fires on a forbidden term in visible page text', () => {
    const dir = fixture({ 'about.html': page('About', '<p>What the odds are.</p>') });
    expectViolation(gate(dir), 'about.html', 'copy-safety', '"odds"');
  });

  it('fires on a forbidden term inside a payload string literal', () => {
    const dir = fixture({ 'about.txt': rsc('This predicts the outcome.') });
    expectViolation(gate(dir), 'about.txt', 'copy-safety in payload string', 'predict');
  });

  it('fires on a forbidden term inside an RSC T row (byte-length body)', () => {
    const body = 'Café notes: a guaranteed result.';
    const raw = `3:T${Buffer.byteLength(body, 'utf8').toString(16)},${body}4:["$","p",null,{}]\n`;
    const dir = fixture({ 'about.txt': raw });
    expectViolation(gate(dir), 'about.txt', 'guarantee');
  });

  it('fires on a forbidden term in a data-file string value, with its path', () => {
    const index = JSON.parse(CLEAN_FILES['data/search-index.json'] as string) as {
      charges: Array<{ displayName: string }>;
    };
    index.charges[0]!.displayName = 'Alpha Charge (win rate)';
    const dir = fixture({ 'data/search-index.json': JSON.stringify(index) });
    expectViolation(gate(dir), 'data/search-index.json', 'copy-safety at $.charges[0].displayName');
  });
});

describe('baked failure states (pin 3.A.5, visible text only)', () => {
  it('fires on the transport-failure message baked into a page', () => {
    const dir = fixture({ 'about.html': page('About', `<p>${FETCH_FAILURE_MESSAGE}</p>`) });
    expectViolation(gate(dir), 'about.html', 'baked failure state', FETCH_FAILURE_MESSAGE);
  });

  it('fires on error-boundary chrome, a catalog error message, and the root 404 copy outside the 404 pages', () => {
    const dir = fixture({
      'charges.html': page('Charges', `<h2>${ERROR_BOUNDARY_COPY.heading}</h2>`),
      'about.html': page('About', `<p>${PUBLIC_ERROR_MESSAGES.INTERNAL_ERROR}</p>`),
      'index.html': page('Search', `<p>${ROOT_NOT_FOUND_MESSAGE}</p>`),
    });
    const result = gate(dir);
    expectViolation(result, 'charges.html', ERROR_BOUNDARY_COPY.heading);
    expectViolation(result, 'about.html', PUBLIC_ERROR_MESSAGES.INTERNAL_ERROR);
    expectViolation(result, 'index.html', ROOT_NOT_FOUND_MESSAGE);
  });

  it('does not treat the two designed-state messages as baked failures (plan §1.5 deviation, ruling pending)', () => {
    const dir = fixture({
      'charges/alpha-charge.html': page(
        'Alpha Charge',
        `<p>${CHARGE_SENTENCING_UNAVAILABLE_MESSAGE}</p><p>${CHARGE_RESULT_UNAVAILABLE_MESSAGE}</p>` +
          `<p>${AGGREGATE_RUN_LABEL_PREFIX}${RUN.slice(0, 8)}</p>`,
      ),
    });
    expect(gate(dir).violations).toEqual([]);
    expect(BAKED_STATE_STRINGS).not.toContain(CHARGE_SENTENCING_UNAVAILABLE_MESSAGE);
    expect(BAKED_STATE_STRINGS).not.toContain(CHARGE_RESULT_UNAVAILABLE_MESSAGE);
    expect(BAKED_STATE_STRINGS).toContain(FETCH_FAILURE_MESSAGE);
    expect(BAKED_STATE_STRINGS).toContain(PUBLIC_ERROR_MESSAGES.RATE_LIMITED);
    expect(BAKED_STATE_STRINGS).toContain(ROOT_NOT_FOUND_HEADING);
  });
});

describe('run identity (pin 3.A.4)', () => {
  it('fires when a data file carries another run', () => {
    const dir = fixture({
      'data/charges/alpha-charge.json': JSON.stringify({
        aggregateRunId: OTHER_RUN,
        chargeSlug: 'alpha-charge',
        judges: {},
      }),
    });
    expectViolation(gate(dir), 'data/charges/alpha-charge.json', 'aggregateRunId is ffffffff');
  });

  it("fires when a page's provenance line names another run", () => {
    const dir = fixture({
      'charges/alpha-charge.html': page(
        'Alpha Charge',
        `<p>${AGGREGATE_RUN_LABEL_PREFIX}${OTHER_RUN.slice(0, 8)}</p>`,
      ),
    });
    expectViolation(gate(dir), 'charges/alpha-charge.html', 'provenance names run ffffffff');
  });
});

describe('coverage both ways (pin 3.A.3)', () => {
  it('fires on a manifest route with no page', () => {
    const manifest = cleanManifest();
    manifest.routes.push('/charges/beta-charge');
    expectViolation(gate(fixture(), manifest), 'charges/beta-charge.html', 'missing');
  });

  it('fires on a page the manifest does not name', () => {
    const dir = fixture({ 'extra.html': page('Extra', '<p>extra</p>') });
    expectViolation(gate(dir), 'extra.html', 'page not named by the manifest');
  });

  it('fires on data files the manifest does not name, and on named data files that are missing', () => {
    const extra = fixture({
      'data/charges/beta-charge.json': JSON.stringify({
        aggregateRunId: RUN,
        chargeSlug: 'beta-charge',
        judges: {},
      }),
    });
    expectViolation(gate(extra), 'data/charges/beta-charge.json', 'not named by the manifest');
    const missing = fixture({ 'data/charges/alpha-charge.json': null });
    expectViolation(gate(missing), 'data/charges/alpha-charge.json', 'missing');
  });

  it('fires on files outside every pattern and outside the allowed set', () => {
    const dir = fixture({
      'stray.txt': 'stray',
      'nope/__next._tree.txt': rsc('tree'),
      'notes.md': '# notes',
    });
    const result = gate(dir);
    expectViolation(result, 'stray.txt', 'outside every route pattern');
    expectViolation(result, 'nope/__next._tree.txt', 'outside every route pattern');
    expectViolation(result, 'notes.md', 'allowed set');
  });
});

describe('noindex and platform files (pin 3.A.6)', () => {
  it('fires on a page without the robots meta', () => {
    const dir = fixture({ 'about.html': page('About', '<p>about</p>', { robots: false }) });
    expectViolation(gate(dir), 'about.html', 'no robots meta');
  });

  it('fires when _headers lacks the X-Robots-Tag rule or is missing', () => {
    expectViolation(
      gate(fixture({ _headers: '/*\n  Cache-Control: no-store\n' })),
      '_headers',
      'X-Robots-Tag',
    );
    expectViolation(gate(fixture({ _headers: null })), '_headers', 'missing');
  });

  it('fires when _redirects lacks the legacy judge rule', () => {
    expectViolation(
      gate(fixture({ _redirects: '/old /new 301\n' })),
      '_redirects',
      'legacy judge rule',
    );
  });
});

describe('limits (pin 3.A.7)', () => {
  it('fires on a file over the size limit, naming it', () => {
    const result = gate(fixture(), cleanManifest(), { maxFileBytes: 10 });
    expectViolation(result, 'exceeds the per-file limit of 10');
  });

  it('fires when the export has more files than the limit', () => {
    const result = gate(fixture(), cleanManifest(), { maxFiles: 3 });
    expectViolation(result, '24 files exceeds the limit of 3');
  });
});

describe('text helpers', () => {
  it('visibleText drops script, style, template, comments, and tags, and decodes entities', () => {
    const html =
      '<html><head><script>["hidden"]</script><style>.odds{}</style></head>' +
      '<body><!-- c --><template><p>tpl</p></template><p>Tom&#x27;s &amp; Jerry&#39;s <b>show</b>&nbsp;on</p></body></html>';
    expect(visibleText(html)).toBe("Tom's & Jerry's show on");
  });

  it('hasNoindexMeta accepts either attribute order and rejects index', () => {
    expect(hasNoindexMeta('<meta content="noindex, nofollow" name="robots">')).toBe(true);
    expect(hasNoindexMeta('<meta name="robots" content="index, follow">')).toBe(false);
    expect(hasNoindexMeta('<meta name="viewport" content="noindex">')).toBe(false);
  });

  it('payloadStrings yields decoded literals and T-row bodies', () => {
    const body = 'Café text';
    const raw = `2:["$","p",null,{"children":"a \\"quoted\\" word"}]\n3:T${Buffer.byteLength(body, 'utf8').toString(16)},${body}4:[]\n`;
    const strings = payloadStrings(raw);
    expect(strings).toContain('a "quoted" word');
    expect(strings).toContain(body);
  });

  it('platform-file predicates', () => {
    expect(headersHaveNoindexRule('/*\n  X-Robots-Tag: noindex, nofollow\n')).toBe(true);
    expect(headersHaveNoindexRule('/data/*\n  X-Robots-Tag: noindex\n')).toBe(false);
    expect(redirectsHaveLegacyJudgeRule(`# comment\n${LEGACY_JUDGE_REDIRECT}\n`)).toBe(true);
    expect(redirectsHaveLegacyJudgeRule('/a /b 301\n')).toBe(false);
  });
});
