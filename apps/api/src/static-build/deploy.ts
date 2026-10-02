import { readStamp, verifyStamp, type GateStamp } from './stamp.js';

/**
 * The upload step's pre-flight (task STATIC-2c, pin 3.D.13), pure and
 * fail-closed, in this order:
 *   1. a gate stamp exists and vouches, byte for byte, for the directory about
 *      to be uploaded (pin 3.A.8);
 *   2. the stamped build ran in publish mode — a ci-mode export is never
 *      uploaded;
 *   3. `PAGES_PROJECT_NAME` is set in the environment (the gitignored root
 *      `.env` is the intended home; nothing in the repo names the project).
 * Only then is the wrangler invocation assembled — as argv, never a shell
 * string, and never echoed with the project name by this module's errors.
 */
export const PROJECT_NAME_VARIABLE = 'PAGES_PROJECT_NAME';

export interface DeployInputs {
  exportDir: string;
  stampFile: string;
  /** Directory whose `pnpm exec wrangler` is used (the e2e workspace holds wrangler). */
  wranglerCwd: string;
  env: Readonly<Record<string, string | undefined>>;
}

export interface DeployPlan {
  exportDir: string;
  projectName: string;
  stamp: GateStamp;
  command: { cwd: string; file: string; args: string[] };
}

export function planDeploy(inputs: DeployInputs): DeployPlan {
  const stamp = readStamp(inputs.stampFile);
  const verdict = verifyStamp(stamp, inputs.exportDir);
  if (!verdict.ok) {
    throw new Error(`upload refused — ${verdict.reason}`);
  }
  // verifyStamp only passes with a stamp present.
  const verified = stamp as GateStamp;
  if (verified.mode !== 'publish') {
    throw new Error(
      `upload refused — the stamped build ran in "${verified.mode}" mode; only a publish-mode export is uploaded.`,
    );
  }
  const projectName = inputs.env[PROJECT_NAME_VARIABLE]?.trim();
  if (!projectName) {
    throw new Error(
      `upload refused — ${PROJECT_NAME_VARIABLE} is not set (expected in the gitignored root .env).`,
    );
  }
  return {
    exportDir: inputs.exportDir,
    projectName,
    stamp: verified,
    command: {
      cwd: inputs.wranglerCwd,
      file: 'pnpm',
      args: [
        'exec',
        'wrangler',
        'pages',
        'deploy',
        inputs.exportDir,
        '--project-name',
        projectName,
      ],
    },
  };
}

/** The command for a log line, with the project name masked. */
export function describeCommand(plan: DeployPlan): string {
  return plan.command.args
    .map((arg) => (arg === plan.projectName ? `$${PROJECT_NAME_VARIABLE}` : arg))
    .join(' ');
}
