import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';

const SCAN_EXTENSIONS = ['.ts', '.tsx', '.css', '.md'];

const APP_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'app');

function collectSourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectSourceFiles(fullPath));
    } else if (SCAN_EXTENSIONS.includes(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }
  return files;
}

function findViolations(content: string): string[] {
  // Collapse whitespace so multi-word terms and disclaimer phrases still
  // match when source formatting wraps them across lines. This is file-level
  // preprocessing only — all term and guarded-phrase matching lives in the
  // shared scanner (@pca/shared copy-safety, task 10.2).
  const collapsed = content.replace(/\s+/g, ' ');
  return scanPublicCopy(collapsed).map(
    (violation) => `${violation.term} ("${violation.context.trim()}")`,
  );
}

describe('copy guard', () => {
  it('finds source files to scan', () => {
    expect(collectSourceFiles(APP_DIR).length).toBeGreaterThan(0);
  });

  it('contains no forbidden or unguarded terms under app/', () => {
    const failures: string[] = [];
    for (const file of collectSourceFiles(APP_DIR)) {
      const content = readFileSync(file, 'utf8');
      for (const term of findViolations(content)) {
        failures.push(`${path.relative(APP_DIR, file)}: "${term}"`);
      }
    }
    expect(failures, failures.join('\n')).toEqual([]);
  });
});
