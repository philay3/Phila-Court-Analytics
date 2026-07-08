import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { buildArtifacts } from './build.js';
import { loadSeeds, validateAll } from './validation.js';

const seeds = loadSeeds();
const errors = validateAll(seeds);

if (errors.length > 0) {
  console.error(`Refusing to generate: seeds failed validation with ${errors.length} error(s):`);
  for (const error of errors) {
    console.error(`  - ${error}`);
  }
  process.exit(1);
}

const { taxonomyJson, indexTs } = buildArtifacts(seeds);

const generatedDir = fileURLToPath(new URL('../generated/', import.meta.url));
mkdirSync(generatedDir, { recursive: true });
writeFileSync(`${generatedDir}taxonomy.json`, taxonomyJson);
writeFileSync(`${generatedDir}index.ts`, indexTs);

console.log('Generated generated/taxonomy.json and generated/index.ts');
