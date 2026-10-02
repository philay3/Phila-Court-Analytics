import { parseBuildMode } from './guards.js';
import { OUT_DIR, runStaticBuild } from './run.js';

// `pnpm run build:static -- --mode publish|ci` (root) → this file under tsx.
// Console output: statuses, counts, short run ids, database NAME only.
try {
  const mode = parseBuildMode(process.argv.slice(2));
  const summary = await runStaticBuild(mode);
  console.log('static-build: summary');
  console.log(`  mode:            ${summary.mode}`);
  console.log(`  database:        ${summary.database}`);
  console.log(`  published run:   ${summary.aggregateRunId}`);
  console.log(`  routes (html):   ${summary.routes}`);
  console.log(`  data files:      ${summary.dataFiles}`);
  console.log(`  total files:     ${summary.totalFiles}`);
  console.log(`  largest file:    ${summary.largestFile.bytes} bytes  ${summary.largestFile.path}`);
  console.log(`  api injects:     ${summary.injected}; served to next build: ${summary.served}`);
  console.log(`  export dir:      ${OUT_DIR}`);
  console.log(`  manifest:        ${summary.manifestFile}`);
  process.exit(0);
} catch (error) {
  console.error(`static-build: FAILED — ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
