import { readFileSync, writeFileSync } from 'node:fs';
import type { BuildMode } from './guards.js';

/**
 * The build's own account of what it meant to export (task STATIC-2c, pin
 * 3.A.3). Written to the ignored scratch directory — never into the upload set
 * — from what the build INTENDED (the routes it enumerated from the search
 * index, the data files it wrote, the run it pinned), so the gate's two-way
 * coverage check compares the export against an independent list rather than
 * against a walk of the export itself. `assets` is the one listing taken from
 * the export right after `next build`: Next's `_next/` output and the
 * `public/` copies, which no other source can enumerate beforehand.
 */
export const MANIFEST_VERSION = 1;

export interface ExportManifest {
  version: typeof MANIFEST_VERSION;
  mode: BuildMode;
  /** The pinned published run every page and data file must carry. */
  aggregateRunId: string;
  generatedAt: string;
  /** Route paths: '/', '/about', '/charges', '/charges/<slug>', … */
  routes: string[];
  /** Not-found pages Next emits beside the routes (export-relative). */
  notFound: string[];
  /** Files the build wrote under data/ (export-relative). */
  dataFiles: string[];
  /** Every other file the export may carry (export-relative): the allowed set, nothing more. */
  assets: string[];
}

/** The pinned static routes (STATIC-2b); charge pages are added per search-index entry. */
export const STATIC_ROUTES: readonly string[] = [
  '/',
  '/about',
  '/charges',
  '/data-coverage',
  '/definitions',
  '/methodology',
];

/** `404.html` is what Cloudflare Pages serves for unknown paths; `_not-found.html` is Next's boundary page. */
export const NOT_FOUND_PAGES: readonly string[] = ['404.html', '_not-found.html'];

export function writeManifest(file: string, manifest: ExportManifest): void {
  writeFileSync(file, `${JSON.stringify(manifest, null, 2)}\n`);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

/** Reads and shape-checks a manifest; a malformed file is a hard failure, never a lenient default. */
export function readManifest(file: string): ExportManifest {
  const parsed: unknown = JSON.parse(readFileSync(file, 'utf8'));
  if (parsed === null || typeof parsed !== 'object') {
    throw new Error(`manifest ${file} is not an object`);
  }
  const m = parsed as Record<string, unknown>;
  if (m.version !== MANIFEST_VERSION) {
    throw new Error(
      `manifest ${file} has version ${String(m.version)}; expected ${MANIFEST_VERSION}`,
    );
  }
  if (m.mode !== 'publish' && m.mode !== 'ci') {
    throw new Error(`manifest ${file} has an unknown mode ${String(m.mode)}`);
  }
  if (typeof m.aggregateRunId !== 'string' || m.aggregateRunId.length === 0) {
    throw new Error(`manifest ${file} carries no aggregateRunId`);
  }
  for (const key of ['routes', 'notFound', 'dataFiles', 'assets'] as const) {
    if (!isStringArray(m[key])) {
      throw new Error(`manifest ${file}: "${key}" is not a list of strings`);
    }
  }
  return {
    version: MANIFEST_VERSION,
    mode: m.mode,
    aggregateRunId: m.aggregateRunId,
    generatedAt: typeof m.generatedAt === 'string' ? m.generatedAt : '',
    routes: m.routes as string[],
    notFound: m.notFound as string[],
    dataFiles: m.dataFiles as string[],
    assets: m.assets as string[],
  };
}
