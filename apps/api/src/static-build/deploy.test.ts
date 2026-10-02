import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { PROJECT_NAME_VARIABLE, describeCommand, planDeploy } from './deploy.js';
import { digestExport, writeStamp, type GateStamp } from './stamp.js';

// An invented export (one page, one data file) with a stamp written the way
// the gate writes it. The project name is a made-up marker so the tests can
// assert it never leaks into an error message.
const PROJECT = 'fictional-project-marker';
const RUN = '0f1e2d3c-0000-4000-8000-00000000c0de';

const dirs: string[] = [];
afterEach(() => {
  for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

function exportDir(): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'pca-deploy-'));
  dirs.push(dir);
  const out = path.join(dir, 'out');
  mkdirSync(path.join(out, 'data'), { recursive: true });
  writeFileSync(path.join(out, 'index.html'), '<html><body>Search</body></html>');
  writeFileSync(path.join(out, 'data', 'search-index.json'), '{"aggregateRunId":"x"}');
  return out;
}

function stampFor(out: string, overrides: Partial<GateStamp> = {}): string {
  const digest = digestExport(out);
  const file = path.join(path.dirname(out), 'gate-stamp.json');
  writeStamp(file, {
    version: 1,
    exportDir: out,
    contentHash: digest.contentHash,
    fileCount: digest.fileCount,
    totalBytes: digest.totalBytes,
    mode: 'publish',
    aggregateRunId: RUN,
    gatedAt: '2026-01-01T00:00:00.000Z',
    ...overrides,
  });
  return file;
}

function inputs(out: string, stampFile: string, env: Record<string, string | undefined>) {
  return { exportDir: out, stampFile, wranglerCwd: '/repo/e2e', env };
}

describe('planDeploy — refusals before wrangler is ever invoked', () => {
  it('refuses without a gate stamp', () => {
    const out = exportDir();
    expect(() =>
      planDeploy(
        inputs(out, path.join(path.dirname(out), 'missing-stamp.json'), {
          [PROJECT_NAME_VARIABLE]: PROJECT,
        }),
      ),
    ).toThrowError(/upload refused — no gate stamp/);
  });

  it('refuses when the export changed after the gate passed', () => {
    const out = exportDir();
    const stamp = stampFor(out);
    writeFileSync(path.join(out, 'index.html'), '<html><body>Changed</body></html>');
    expect(() => planDeploy(inputs(out, stamp, { [PROJECT_NAME_VARIABLE]: PROJECT }))).toThrowError(
      /changed since the gate passed/,
    );
  });

  it('refuses when a file was added after the gate passed', () => {
    const out = exportDir();
    const stamp = stampFor(out);
    writeFileSync(path.join(out, 'extra.html'), '<html></html>');
    expect(() => planDeploy(inputs(out, stamp, { [PROJECT_NAME_VARIABLE]: PROJECT }))).toThrowError(
      /changed since the gate passed/,
    );
  });

  it('refuses a stamp for a different directory', () => {
    const out = exportDir();
    const other = exportDir();
    const stamp = stampFor(other);
    expect(() => planDeploy(inputs(out, stamp, { [PROJECT_NAME_VARIABLE]: PROJECT }))).toThrowError(
      /is for .* not /,
    );
  });

  it('refuses a ci-mode export', () => {
    const out = exportDir();
    const stamp = stampFor(out, { mode: 'ci' });
    expect(() => planDeploy(inputs(out, stamp, { [PROJECT_NAME_VARIABLE]: PROJECT }))).toThrowError(
      /ran in "ci" mode/,
    );
  });

  it('refuses without PAGES_PROJECT_NAME, and no message names a project', () => {
    const out = exportDir();
    const stamp = stampFor(out);
    for (const env of [{}, { [PROJECT_NAME_VARIABLE]: '   ' }]) {
      let message = '';
      try {
        planDeploy(inputs(out, stamp, env));
      } catch (error) {
        message = (error as Error).message;
      }
      expect(message).toMatch(/PAGES_PROJECT_NAME is not set/);
      expect(message).not.toContain(PROJECT);
    }
  });
});

describe('planDeploy — the accepted path', () => {
  it('assembles the wrangler invocation as argv and masks the project name in the log form', () => {
    const out = exportDir();
    const stamp = stampFor(out);
    const plan = planDeploy(inputs(out, stamp, { [PROJECT_NAME_VARIABLE]: PROJECT }));
    expect(plan.projectName).toBe(PROJECT);
    expect(plan.command).toEqual({
      cwd: '/repo/e2e',
      file: 'pnpm',
      args: ['exec', 'wrangler', 'pages', 'deploy', out, '--project-name', PROJECT],
    });
    expect(plan.stamp.aggregateRunId).toBe(RUN);
    const described = describeCommand(plan);
    expect(described).toContain('--project-name $PAGES_PROJECT_NAME');
    expect(described).not.toContain(PROJECT);
  });
});
