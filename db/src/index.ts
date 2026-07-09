// Public entry point of @pca/db (task 7.2). Exposes exactly what other
// workspace packages may consume: the typed Database shape and the idempotent
// reference seeder (used by API test setups so CI needs no separate seed step).
// Everything else — migrations, seed data/values, connection internals — stays
// package-private.
export type { Database } from './types.js';
export { seedReference } from '../seeds/reference.js';
export { seedAggregates } from '../seeds/aggregates.js';
