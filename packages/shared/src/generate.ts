import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { FORBIDDEN_FIELD_STEMS, FORBIDDEN_VALUE_PATTERNS } from './public/forbidden-fields.js';

// Emits generated/forbidden-fields.json (task 28.1), mirroring the taxonomy
// package's generate script: a gitignored, build-time JSON artifact consumed
// by the Python pipeline's forbidden-field scanner port
// (services/pipeline/src/pipeline/forbidden_scan.py). The TS constants in
// src/public/forbidden-fields.ts remain the single source of truth; this
// script only serializes them, so the Python side can never drift from the
// list the API privacy suites enforce.
//
// Value patterns are emitted as { source, flags } pairs. The shared patterns
// deliberately use only regex constructs with identical semantics in
// JavaScript and Python `re` (\b, (?:), \d, character classes, bounded
// repetition, the `i` flag); anything fancier must be weighed against the
// Python consumer before it lands in forbidden-fields.ts.

const artifact = {
  fieldStems: [...FORBIDDEN_FIELD_STEMS],
  valuePatterns: FORBIDDEN_VALUE_PATTERNS.map((pattern) => ({
    source: pattern.source,
    flags: pattern.flags,
  })),
};

const generatedDir = fileURLToPath(new URL('../generated/', import.meta.url));
mkdirSync(generatedDir, { recursive: true });
writeFileSync(`${generatedDir}forbidden-fields.json`, `${JSON.stringify(artifact, null, 2)}\n`);

console.log('Generated generated/forbidden-fields.json');
