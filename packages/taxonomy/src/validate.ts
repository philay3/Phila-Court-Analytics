import { loadSeeds, validateAll } from './validation.js';

const errors = validateAll(loadSeeds());

if (errors.length > 0) {
  console.error(`Taxonomy validation failed with ${errors.length} error(s):`);
  for (const error of errors) {
    console.error(`  - ${error}`);
  }
  process.exit(1);
}

console.log('Taxonomy seeds are valid.');
