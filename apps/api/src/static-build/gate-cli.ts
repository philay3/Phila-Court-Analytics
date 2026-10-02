import { existsSync } from 'node:fs';
import path from 'node:path';
import { formatSummary, runExportGate } from './gate.js';
import { readManifest } from './manifest.js';
import { OUT_DIR, SCRATCH_DIR } from './run.js';
import { digestExport, writeStamp } from './stamp.js';

// `pnpm run gate:static` (root) → this file under tsx. Runs between the build
// and the upload (publish flow) and after the ci-mode build (CI). Options:
//   --export <dir>      export directory   (default apps/web/out)
//   --manifest <file>   build manifest     (default apps/web/.static-build/manifest.json)
//   --stamp <file>      stamp to write     (default apps/web/.static-build/gate-stamp.json)
//   --no-stamp          check only, write nothing
// Console output: counts, paths, run ids; forbidden VALUES are never printed.

function option(name: string): string | undefined {
  const at = process.argv.indexOf(name);
  return at >= 0 ? process.argv[at + 1] : undefined;
}

const exportDir = path.resolve(option('--export') ?? OUT_DIR);
const manifestFile = path.resolve(option('--manifest') ?? path.join(SCRATCH_DIR, 'manifest.json'));
const stampFile = path.resolve(option('--stamp') ?? path.join(SCRATCH_DIR, 'gate-stamp.json'));
const writeStampFile = !process.argv.includes('--no-stamp');

try {
  if (!existsSync(manifestFile)) {
    throw new Error(
      `no manifest at ${manifestFile}; run the build first (the gate never infers one).`,
    );
  }
  const manifest = readManifest(manifestFile);
  const result = runExportGate({ exportDir, manifest });
  console.log('static-gate: summary');
  for (const line of formatSummary(result.summary)) {
    console.log(`  ${line}`);
  }
  if (!result.ok) {
    const shown = result.violations.slice(0, 200);
    console.error(`static-gate: FAIL — ${result.violations.length} violation(s):`);
    for (const violation of shown) {
      console.error(`  - ${violation}`);
    }
    if (result.violations.length > shown.length) {
      console.error(`  … and ${result.violations.length - shown.length} more`);
    }
    process.exit(1);
  }
  if (writeStampFile) {
    const digest = digestExport(exportDir);
    writeStamp(stampFile, {
      version: 1,
      exportDir,
      contentHash: digest.contentHash,
      fileCount: digest.fileCount,
      totalBytes: digest.totalBytes,
      mode: manifest.mode,
      aggregateRunId: manifest.aggregateRunId,
      gatedAt: new Date().toISOString(),
    });
    console.log(
      `static-gate: PASS — stamp written to ${stampFile} (sha256 ${digest.contentHash.slice(0, 16)}…, ${digest.fileCount} files)`,
    );
  } else {
    console.log('static-gate: PASS (no stamp written: --no-stamp)');
  }
  process.exit(0);
} catch (error) {
  console.error(`static-gate: FAILED — ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
