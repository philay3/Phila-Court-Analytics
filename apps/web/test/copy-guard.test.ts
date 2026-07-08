import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { DISCLAIMER_ALLOWLIST, FORBIDDEN_TERMS, GUARDED_STEM } from './copy-terms';

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

function findAllIndexes(haystack: string, needle: string): number[] {
  const indexes: number[] = [];
  for (let i = haystack.indexOf(needle); i !== -1; i = haystack.indexOf(needle, i + 1)) {
    indexes.push(i);
  }
  return indexes;
}

function findViolations(content: string): string[] {
  // Collapse whitespace so multi-word terms and disclaimer phrases still
  // match when source formatting wraps them across lines.
  const lower = content.toLowerCase().replace(/\s+/g, ' ');
  const violations: string[] = [];

  for (const term of FORBIDDEN_TERMS) {
    if (lower.includes(term.toLowerCase())) {
      violations.push(term);
    }
  }

  const allowedRanges = DISCLAIMER_ALLOWLIST.flatMap((phrase) => {
    const lowerPhrase = phrase.toLowerCase();
    return findAllIndexes(lower, lowerPhrase).map(
      (start) => [start, start + lowerPhrase.length] as const,
    );
  });

  for (const start of findAllIndexes(lower, GUARDED_STEM)) {
    const end = start + GUARDED_STEM.length;
    const allowed = allowedRanges.some(
      ([rangeStart, rangeEnd]) => start >= rangeStart && end <= rangeEnd,
    );
    if (!allowed) {
      violations.push(`${GUARDED_STEM} (outside disclaimer allowlist)`);
    }
  }

  return violations;
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
