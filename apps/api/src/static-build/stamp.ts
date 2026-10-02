import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import type { BuildMode } from './guards.js';

/**
 * The gate stamp (task STATIC-2c, pin 3.A.8): written only when the gate
 * passed, into the ignored scratch directory, carrying a content hash of the
 * export it passed. The upload step recomputes the hash over the directory it
 * is about to upload and refuses on any difference — so nothing that was not
 * gated byte-for-byte can reach the upload.
 */
export const STAMP_VERSION = 1;

export interface GateStamp {
  version: typeof STAMP_VERSION;
  /** Absolute path of the export the hash was taken over. */
  exportDir: string;
  /** SHA-256 over the sorted list of `relativePath \0 sha256(bytes) \n`. */
  contentHash: string;
  fileCount: number;
  totalBytes: number;
  mode: BuildMode;
  aggregateRunId: string;
  gatedAt: string;
}

/** Every file under `dir`, export-relative, POSIX separators, sorted. */
export function listFiles(dir: string): string[] {
  const acc: string[] = [];
  const walk = (current: string): void => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile()) {
        acc.push(path.relative(dir, full).split(path.sep).join('/'));
      }
    }
  };
  walk(dir);
  return acc.sort();
}

export interface ExportDigest {
  contentHash: string;
  fileCount: number;
  totalBytes: number;
}

export function digestExport(dir: string): ExportDigest {
  const files = listFiles(dir);
  const outer = createHash('sha256');
  let totalBytes = 0;
  for (const rel of files) {
    const full = path.join(dir, rel);
    const bytes = readFileSync(full);
    totalBytes += statSync(full).size;
    outer.update(`${rel}\0${createHash('sha256').update(bytes).digest('hex')}\n`);
  }
  return { contentHash: outer.digest('hex'), fileCount: files.length, totalBytes };
}

export function writeStamp(file: string, stamp: GateStamp): void {
  writeFileSync(file, `${JSON.stringify(stamp, null, 2)}\n`);
}

/** The stamp, or null when there is none — the caller decides what that means. */
export function readStamp(file: string): GateStamp | null {
  if (!existsSync(file)) {
    return null;
  }
  const parsed = JSON.parse(readFileSync(file, 'utf8')) as Partial<GateStamp>;
  if (
    parsed.version !== STAMP_VERSION ||
    typeof parsed.contentHash !== 'string' ||
    typeof parsed.fileCount !== 'number' ||
    typeof parsed.exportDir !== 'string' ||
    (parsed.mode !== 'publish' && parsed.mode !== 'ci') ||
    typeof parsed.aggregateRunId !== 'string'
  ) {
    throw new Error(`gate stamp ${file} is malformed; re-run the gate.`);
  }
  return parsed as GateStamp;
}

export type StampVerdict = { ok: true; digest: ExportDigest } | { ok: false; reason: string };

/** Does `stamp` vouch for the export at `exportDir`, byte for byte, right now? */
export function verifyStamp(stamp: GateStamp | null, exportDir: string): StampVerdict {
  if (stamp === null) {
    return {
      ok: false,
      reason: 'no gate stamp: the gate has not passed this export (run the gate first).',
    };
  }
  if (path.resolve(stamp.exportDir) !== path.resolve(exportDir)) {
    return { ok: false, reason: `the gate stamp is for ${stamp.exportDir}, not ${exportDir}.` };
  }
  if (!existsSync(exportDir)) {
    return { ok: false, reason: `export directory ${exportDir} does not exist.` };
  }
  const digest = digestExport(exportDir);
  if (digest.fileCount !== stamp.fileCount || digest.contentHash !== stamp.contentHash) {
    return {
      ok: false,
      reason:
        `the export changed since the gate passed (stamped ${stamp.fileCount} files, ` +
        `${stamp.contentHash.slice(0, 12)}…; now ${digest.fileCount} files, ${digest.contentHash.slice(0, 12)}…). Re-run the gate.`,
    };
  }
  return { ok: true, digest };
}
