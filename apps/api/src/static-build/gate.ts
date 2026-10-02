import { existsSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import {
  AGGREGATE_RUN_LABEL_PREFIX,
  CHARGES_DIRECTORY_ERROR_BODY,
  CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  CONTENT_PAGE_FAILURE_HEADINGS,
  DATA_COVERAGE_UNAVAILABLE_MESSAGE,
  ERROR_BOUNDARY_COPY,
  FETCH_FAILURE_MESSAGE,
  PUBLIC_ERROR_MESSAGES,
  ROOT_NOT_FOUND_HEADING,
  ROOT_NOT_FOUND_HOME_LINK_TEXT,
  ROOT_NOT_FOUND_MESSAGE,
  scanPublicCopy,
} from '@pca/shared';
import { scanForForbidden, type ForbiddenViolation } from '@pca/shared/forbidden-scan';
import type { ExportManifest } from './manifest.js';
import { listFiles } from './stamp.js';

/**
 * The export gate (task STATIC-2c, pin 3.A). Walks every file of an export
 * directory against the build's manifest and fails closed on any violation:
 *
 *   - `.html`: visible text (script/style/template/comments dropped, tags
 *     stripped, entities decoded) through `scanPublicCopy`; the raw file
 *     through `scanForForbidden` (the embedded flight data counts); the
 *     provenance line must name the pinned run; the robots meta must say
 *     `noindex`; no baked error / not-found state in the visible text (the two
 *     not-found pages exempt);
 *   - `.txt` / `.rsc` payloads: `scanForForbidden` over the raw text;
 *     `scanPublicCopy` over every JSON string literal and every RSC `T` row;
 *   - `data/*.json`: `scanForForbidden` over the parsed document;
 *     `scanPublicCopy` over every string value; `aggregateRunId` pinned;
 *   - everything else: named in the manifest's `assets`, nothing more;
 *   - coverage both ways between the manifest and the export; `_headers` and
 *     `_redirects` rules present; file-count and file-size limits.
 *
 * Scanners come from @pca/shared — no term list is defined here.
 */

export interface GateLimits {
  maxFiles: number;
  maxFileBytes: number;
}

export const GATE_LIMITS: GateLimits = { maxFiles: 15_000, maxFileBytes: 20 * 1024 * 1024 };

/**
 * Pin 3.A.5, with one recorded deviation (STATIC-2c plan §1.5, ruling
 * pending): these two PUBLIC_ERROR_MESSAGES values are ALSO pinned
 * designed-state copy that a successful charge-only payload renders by design
 * (the sentencing-unavailable arm; the charge-only unavailable arm), so they
 * are not treated as baked error states. Remove an entry here to enforce it.
 */
export const DESIGNED_STATE_MESSAGES: readonly string[] = [
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
];

/** Strings whose presence in a page's visible text means a failure state was baked. */
export const BAKED_STATE_STRINGS: readonly string[] = [
  ...new Set([
    FETCH_FAILURE_MESSAGE,
    ...Object.values(PUBLIC_ERROR_MESSAGES).filter((m) => !DESIGNED_STATE_MESSAGES.includes(m)),
    CHARGES_DIRECTORY_ERROR_BODY,
    CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
    DATA_COVERAGE_UNAVAILABLE_MESSAGE,
    ...Object.values(CONTENT_PAGE_FAILURE_HEADINGS),
    ROOT_NOT_FOUND_HEADING,
    ROOT_NOT_FOUND_MESSAGE,
    ROOT_NOT_FOUND_HOME_LINK_TEXT,
    ...Object.values(ERROR_BOUNDARY_COPY),
  ]),
];

export const HEADERS_FILE = '_headers';
export const REDIRECTS_FILE = '_redirects';
export const ROBOTS_HEADER_RULE = /^\s*X-Robots-Tag:\s*noindex\b/im;
export const LEGACY_JUDGE_REDIRECT =
  '/charges/:charge/judge/:judge /charges/:charge?judge=:judge 301';

export interface GateSummary {
  exportDir: string;
  mode: ExportManifest['mode'];
  aggregateRunId: string;
  walked: { html: number; payload: number; data: number; asset: number };
  pagesChecked: number;
  pagesUnderBakedStateRule: number;
  dataFilesChecked: number;
  totalFiles: number;
  totalBytes: number;
  largestFile: { path: string; bytes: number };
  limits: GateLimits;
}

export interface GateResult {
  ok: boolean;
  violations: string[];
  summary: GateSummary;
}

export interface GateOptions {
  exportDir: string;
  manifest: ExportManifest;
  limits?: Partial<GateLimits>;
}

// ---------------------------------------------------------------------------
// Text helpers (exported for the tests).
// ---------------------------------------------------------------------------

const NAMED_ENTITIES: Record<string, string> = {
  quot: '"',
  apos: "'",
  lt: '<',
  gt: '>',
  nbsp: ' ',
  hellip: '…',
  ndash: '–',
  mdash: '—',
};

export function decodeEntities(text: string): string {
  return text
    .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec: string) => String.fromCodePoint(parseInt(dec, 10)))
    .replace(/&([a-z]+);/gi, (whole, name: string) => NAMED_ENTITIES[name.toLowerCase()] ?? whole)
    .replace(/&amp;/g, '&');
}

/** What a reader sees: no script, style, or template content, no tags, entities decoded, whitespace collapsed. */
export function visibleText(html: string): string {
  const stripped = html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style\s*>/gi, ' ')
    .replace(/<template\b[^>]*>[\s\S]*?<\/template\s*>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]+>/g, ' ');
  return decodeEntities(stripped).replace(/\s+/g, ' ').trim();
}

export function hasNoindexMeta(html: string): boolean {
  for (const tag of html.match(/<meta\b[^>]*>/gi) ?? []) {
    const name = /\bname\s*=\s*["']?robots["']?/i.test(tag);
    const content = /\bcontent\s*=\s*["']([^"']*)["']/i.exec(tag)?.[1] ?? '';
    if (name && /\bnoindex\b/i.test(content)) {
      return true;
    }
  }
  return false;
}

/**
 * Every string a React Flight payload carries as text: JSON string literals
 * (decoded) and the bodies of `T` rows (`<id>:T<hexByteLength>,<text>` — the
 * length counts UTF-8 bytes, so the body is sliced from the byte buffer).
 */
export function payloadStrings(raw: string): string[] {
  const out: string[] = [];
  for (const literal of raw.match(/"(?:[^"\\\n]|\\.)*"/g) ?? []) {
    try {
      const value: unknown = JSON.parse(literal);
      if (typeof value === 'string' && value.length > 0) {
        out.push(value);
      }
    } catch {
      // Not a complete JSON literal (e.g. a quote inside a T row body); skipped.
    }
  }
  const buffer = Buffer.from(raw, 'utf8');
  for (const row of raw.matchAll(/(?:^|\n)[0-9a-f]+:T([0-9a-f]+),/g)) {
    const bodyStart = Buffer.byteLength(raw.slice(0, row.index + row[0].length), 'utf8');
    const length = parseInt(row[1] ?? '0', 16);
    const body = buffer.subarray(bodyStart, bodyStart + length).toString('utf8');
    if (body.length > 0) {
      out.push(body);
    }
  }
  return out;
}

/** The `scanJsonStrings` walk: every string value in a parsed document, with its path. */
export function jsonStrings(
  value: unknown,
  pathPrefix = '$',
): Array<{ path: string; value: string }> {
  if (typeof value === 'string') {
    return [{ path: pathPrefix, value }];
  }
  if (Array.isArray(value)) {
    return value.flatMap((entry, index) => jsonStrings(entry, `${pathPrefix}[${index}]`));
  }
  if (value !== null && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, entry]) =>
      jsonStrings(entry, `${pathPrefix}.${key}`),
    );
  }
  return [];
}

function escapeRegExp(literal: string): string {
  return literal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Forbidden-content hits, with the offending VALUE redacted: a gate log must never carry what it caught. */
function describeForbidden(hits: ForbiddenViolation[]): string {
  return hits
    .slice(0, 5)
    .map((hit) =>
      hit.kind === 'key'
        ? `forbidden key "${hit.offender}" at ${hit.jsonPath} (stem ${hit.matched})`
        : `forbidden value shape at ${hit.jsonPath} (${hit.offender.length} chars, pattern ${hit.matched})`,
    )
    .join('; ');
}

function describeCopy(hits: ReturnType<typeof scanPublicCopy>): string {
  return hits
    .slice(0, 5)
    .map((hit) => `"${hit.term}" at ${hit.index} (…${hit.context.replace(/\s+/g, ' ')}…)`)
    .join('; ');
}

// ---------------------------------------------------------------------------
// Classification by the manifest + the segment-file pattern (plan §1.3).
// ---------------------------------------------------------------------------

type FileKind = 'html' | 'payload' | 'data' | 'asset';

interface Expectations {
  /** `<base>.html` → route (or the not-found marker). */
  pages: Map<string, string>;
  notFoundPages: Set<string>;
  /** `<base>.txt` page payloads. */
  pagePayloads: Set<string>;
  /** Directory prefix ('' for the root) → route, for `__next.<name>.txt` segment files. */
  segmentDirs: Map<string, string>;
  dataFiles: Set<string>;
  assets: Set<string>;
}

export function routeBase(route: string): string {
  return route === '/' ? 'index' : route.replace(/^\//, '');
}

function expectationsFor(manifest: ExportManifest): Expectations {
  const pages = new Map<string, string>();
  const pagePayloads = new Set<string>();
  const segmentDirs = new Map<string, string>();
  for (const route of manifest.routes) {
    const base = routeBase(route);
    pages.set(`${base}.html`, route);
    pagePayloads.add(`${base}.txt`);
    segmentDirs.set(route === '/' ? '' : `${base}/`, route);
  }
  const notFoundPages = new Set(manifest.notFound);
  // Next's not-found boundary follows the route shape under `_not-found`.
  pagePayloads.add('_not-found.txt');
  segmentDirs.set('_not-found/', '(not-found)');
  return {
    pages,
    notFoundPages,
    pagePayloads,
    segmentDirs,
    dataFiles: new Set(manifest.dataFiles),
    assets: new Set(manifest.assets),
  };
}

const SEGMENT_FILE = /^__next\.[^/]+\.txt$/;

function classify(rel: string, expected: Expectations): FileKind | null {
  if (rel.endsWith('.html')) {
    return expected.pages.has(rel) || expected.notFoundPages.has(rel) ? 'html' : null;
  }
  if (rel.startsWith('data/')) {
    return expected.dataFiles.has(rel) ? 'data' : null;
  }
  if (rel.endsWith('.txt') || rel.endsWith('.rsc')) {
    if (expected.pagePayloads.has(rel)) {
      return 'payload';
    }
    const slash = rel.lastIndexOf('/');
    const dir = slash === -1 ? '' : rel.slice(0, slash + 1);
    const name = slash === -1 ? rel : rel.slice(slash + 1);
    return expected.segmentDirs.has(dir) && SEGMENT_FILE.test(name) ? 'payload' : null;
  }
  return expected.assets.has(rel) ? 'asset' : null;
}

// ---------------------------------------------------------------------------
// The gate.
// ---------------------------------------------------------------------------

export function runExportGate(options: GateOptions): GateResult {
  const { exportDir, manifest } = options;
  const limits: GateLimits = { ...GATE_LIMITS, ...options.limits };
  const violations: string[] = [];
  const fail = (rel: string, what: string): void => {
    violations.push(`${rel}: ${what}`);
  };
  const expected = expectationsFor(manifest);
  const pinnedPrefix = manifest.aggregateRunId.slice(0, 8);
  const provenance = new RegExp(`${escapeRegExp(AGGREGATE_RUN_LABEL_PREFIX)}([0-9a-f]{8})`, 'g');

  const files = existsSync(exportDir) ? listFiles(exportDir) : [];
  if (files.length === 0) {
    fail(exportDir, 'export directory is missing or empty');
  }

  const walked = { html: 0, payload: 0, data: 0, asset: 0 };
  let pagesChecked = 0;
  let pagesUnderBakedStateRule = 0;
  let dataFilesChecked = 0;
  let totalBytes = 0;
  let largestFile = { path: '', bytes: -1 };
  const seen = new Set<string>();

  for (const rel of files) {
    seen.add(rel);
    const full = path.join(exportDir, rel);
    const bytes = statSync(full).size;
    totalBytes += bytes;
    if (bytes > largestFile.bytes) {
      largestFile = { path: rel, bytes };
    }
    if (bytes > limits.maxFileBytes) {
      fail(rel, `${bytes} bytes exceeds the per-file limit of ${limits.maxFileBytes}`);
    }

    const kind = classify(rel, expected);
    if (kind === null) {
      fail(
        rel,
        rel.endsWith('.html')
          ? 'page not named by the manifest'
          : rel.startsWith('data/')
            ? 'data file not named by the manifest'
            : rel.endsWith('.txt') || rel.endsWith('.rsc')
              ? 'payload file outside every route pattern'
              : "file not in the manifest's allowed set",
      );
      continue;
    }
    walked[kind] += 1;

    if (kind === 'html') {
      const raw = readFileSync(full, 'utf8');
      const text = visibleText(raw);
      pagesChecked += 1;

      const copyHits = scanPublicCopy(text);
      if (copyHits.length > 0) {
        fail(rel, `copy-safety: ${describeCopy(copyHits)}`);
      }
      const forbidden = scanForForbidden(raw);
      if (forbidden.length > 0) {
        fail(rel, describeForbidden(forbidden));
      }
      for (const match of text.matchAll(provenance)) {
        if (match[1] !== pinnedPrefix) {
          fail(rel, `provenance names run ${match[1]} but the pinned run is ${pinnedPrefix}`);
        }
      }
      if (!hasNoindexMeta(raw)) {
        fail(rel, 'no robots meta with noindex');
      }
      if (!expected.notFoundPages.has(rel)) {
        pagesUnderBakedStateRule += 1;
        for (const baked of BAKED_STATE_STRINGS) {
          if (text.includes(baked)) {
            fail(rel, `baked failure state in visible text: "${baked}"`);
          }
        }
      }
    } else if (kind === 'payload') {
      const raw = readFileSync(full, 'utf8');
      const forbidden = scanForForbidden(raw);
      if (forbidden.length > 0) {
        fail(rel, describeForbidden(forbidden));
      }
      for (const value of payloadStrings(raw)) {
        const hits = scanPublicCopy(value);
        if (hits.length > 0) {
          fail(rel, `copy-safety in payload string: ${describeCopy(hits)}`);
        }
      }
    } else if (kind === 'data') {
      dataFilesChecked += 1;
      let parsed: unknown;
      try {
        parsed = JSON.parse(readFileSync(full, 'utf8'));
      } catch (error) {
        fail(rel, `not valid JSON (${error instanceof Error ? error.message : String(error)})`);
        continue;
      }
      const forbidden = scanForForbidden(parsed);
      if (forbidden.length > 0) {
        fail(rel, describeForbidden(forbidden));
      }
      for (const entry of jsonStrings(parsed)) {
        const hits = scanPublicCopy(entry.value);
        if (hits.length > 0) {
          fail(rel, `copy-safety at ${entry.path}: ${describeCopy(hits)}`);
        }
      }
      const runId =
        parsed !== null && typeof parsed === 'object'
          ? (parsed as { aggregateRunId?: unknown }).aggregateRunId
          : undefined;
      if (runId !== manifest.aggregateRunId) {
        fail(
          rel,
          `aggregateRunId is ${typeof runId === 'string' ? runId.slice(0, 8) : String(runId)} but the pinned run is ${pinnedPrefix}`,
        );
      }
    }
  }

  // Coverage the other way: everything the manifest promises must exist.
  for (const page of [...expected.pages.keys(), ...expected.notFoundPages]) {
    if (!seen.has(page)) {
      fail(page, 'page named by the manifest is missing');
    }
  }
  for (const dataFile of expected.dataFiles) {
    if (!seen.has(dataFile)) {
      fail(dataFile, 'data file named by the manifest is missing');
    }
  }

  // Pin 3.A.6: the platform files.
  const headersPath = path.join(exportDir, HEADERS_FILE);
  if (!existsSync(headersPath)) {
    fail(HEADERS_FILE, 'missing');
  } else if (!headersHaveNoindexRule(readFileSync(headersPath, 'utf8'))) {
    fail(HEADERS_FILE, 'no `X-Robots-Tag: noindex` rule under `/*`');
  }
  const redirectsPath = path.join(exportDir, REDIRECTS_FILE);
  if (!existsSync(redirectsPath)) {
    fail(REDIRECTS_FILE, 'missing');
  } else if (!redirectsHaveLegacyJudgeRule(readFileSync(redirectsPath, 'utf8'))) {
    fail(REDIRECTS_FILE, `no legacy judge rule (expected "${LEGACY_JUDGE_REDIRECT}")`);
  }

  // Pin 3.A.7.
  if (files.length > limits.maxFiles) {
    fail(exportDir, `${files.length} files exceeds the limit of ${limits.maxFiles}`);
  }

  return {
    ok: violations.length === 0,
    violations,
    summary: {
      exportDir,
      mode: manifest.mode,
      aggregateRunId: manifest.aggregateRunId,
      walked,
      pagesChecked,
      pagesUnderBakedStateRule,
      dataFilesChecked,
      totalFiles: files.length,
      totalBytes,
      largestFile,
      limits,
    },
  };
}

/** A `/*` block whose lines include an `X-Robots-Tag: noindex…` header. */
export function headersHaveNoindexRule(headers: string): boolean {
  const blocks = headers.split(/\n(?=\S)/);
  return blocks.some(
    (block) => /^\/\*\s*$/m.test(block.split('\n')[0] ?? '') && ROBOTS_HEADER_RULE.test(block),
  );
}

export function redirectsHaveLegacyJudgeRule(redirects: string): boolean {
  return redirects
    .split('\n')
    .map((line) => line.trim().replace(/\s+/g, ' '))
    .includes(LEGACY_JUDGE_REDIRECT);
}

/** The printed summary (pin 3.A.8), one line per fact. */
export function formatSummary(summary: GateSummary): string[] {
  const w = summary.walked;
  return [
    `export:            ${summary.exportDir}`,
    `mode / run:        ${summary.mode} / ${summary.aggregateRunId}`,
    `files walked:      html ${w.html}, payload ${w.payload}, data ${w.data}, asset ${w.asset}`,
    `pages checked:     ${summary.pagesChecked} (${summary.pagesUnderBakedStateRule} under the baked-state rule; the not-found pages are exempt)`,
    `data files:        ${summary.dataFilesChecked}`,
    `total files:       ${summary.totalFiles} (limit ${summary.limits.maxFiles}); ${summary.totalBytes} bytes`,
    `largest file:      ${summary.largestFile.bytes} bytes  ${summary.largestFile.path} (limit ${summary.limits.maxFileBytes})`,
  ];
}
