import { spawn } from 'node:child_process';
import path from 'node:path';
import { describeCommand, planDeploy } from './deploy.js';
import { OUT_DIR, REPO_ROOT, SCRATCH_DIR } from './run.js';
import { shortRunId } from './guards.js';

// `pnpm run deploy:static` (root) → this file under tsx, after the gate.
//   --dry-run   run every check and print the command (project name masked); upload nothing.
// Console output: paths, counts, short run ids; the project name is never printed.

const dryRun = process.argv.includes('--dry-run');

try {
  const plan = planDeploy({
    exportDir: OUT_DIR,
    stampFile: path.join(SCRATCH_DIR, 'gate-stamp.json'),
    wranglerCwd: path.join(REPO_ROOT, 'e2e'),
    env: process.env,
  });
  console.log(
    `deploy: gate stamp verified — ${plan.stamp.fileCount} files, sha256 ${plan.stamp.contentHash.slice(0, 16)}…, ` +
      `publish mode, run ${shortRunId(plan.stamp.aggregateRunId)}, gated ${plan.stamp.gatedAt}`,
  );
  console.log(
    `deploy: ${dryRun ? 'would run' : 'running'}: pnpm ${describeCommand(plan)} (cwd e2e/)`,
  );
  if (dryRun) {
    process.exit(0);
  }
  const child = spawn(plan.command.file, plan.command.args, {
    cwd: plan.command.cwd,
    stdio: 'inherit',
    env: { ...process.env, WRANGLER_SEND_METRICS: 'false' },
  });
  child.once('error', (error) => {
    console.error(`deploy: FAILED — could not start wrangler: ${error.message}`);
    process.exit(1);
  });
  child.once('exit', (code) => {
    if (code === 0) {
      console.log('deploy: wrangler pages deploy finished');
    } else {
      console.error(`deploy: FAILED — wrangler exited with status ${code ?? 'null'}`);
    }
    process.exit(code ?? 1);
  });
} catch (error) {
  console.error(`deploy: FAILED — ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
