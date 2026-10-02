import { spawn } from 'node:child_process';
import { mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { sql } from 'kysely';
import { SEARCH_INDEX_DATA_PATH, chargeJudgeDataPath } from '@pca/shared';
import { buildApp } from '../app.js';
import { assertDatabaseUrlForMode, shortRunId, type BuildMode } from './guards.js';
import { materializePublicApi, pinPublishedRun } from './materialize.js';
import { startThrowawayApi } from './serve.js';

/**
 * The static build (task STATIC-2b, pin 11), in order and fail-closed at
 * every step:
 *   1. mode flag (parsed by the CLI);
 *   2. the Fastify app in-process, with the limiter raised for this process;
 *   3. database safeguard before any output exists — name-shaped URL check,
 *      `SELECT current_database()` through the app's own handle, data-coverage
 *      `available: true`, run id pinned;
 *   4. materialize every response to a scratch directory (ignored);
 *   5. serve them on a throwaway local server, run `next build` with
 *      `output: 'export'`, stop the server — and fail if the build asked for
 *      anything the server did not have;
 *   6. write the data files under the export's top-level `data/`;
 *   7. print the summary (nothing is pinned in code).
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(HERE, '../../../..');
export const WEB_DIR = path.join(REPO_ROOT, 'apps/web');
export const OUT_DIR = path.join(WEB_DIR, 'out');
export const SCRATCH_DIR = path.join(WEB_DIR, '.static-build');

export interface BuildSummary {
  mode: BuildMode;
  database: string;
  aggregateRunId: string;
  routes: number;
  dataFiles: number;
  totalFiles: number;
  largestFile: { path: string; bytes: number };
  injected: number;
  served: number;
}

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, acc);
    else acc.push(full);
  }
  return acc;
}

export async function runStaticBuild(
  mode: BuildMode,
  log: (line: string) => void = (line) => console.log(`static-build: ${line}`),
): Promise<BuildSummary> {
  // 2. The limiter is always registered (env.ts); raise it for this process only —
  // the build injects thousands of requests in a minute.
  process.env.RATE_LIMIT_MAX = process.env.RATE_LIMIT_MAX ?? '1000000';

  // 3a. Name-shaped, pre-connection.
  const database = assertDatabaseUrlForMode(process.env.DATABASE_URL, mode);
  log(`mode ${mode}; database "${database}" accepted by the ${mode} rule`);

  // Scratch and output are ignored paths; clean before every run (pin 13).
  rmSync(OUT_DIR, { recursive: true, force: true });
  rmSync(SCRATCH_DIR, { recursive: true, force: true });
  mkdirSync(SCRATCH_DIR, { recursive: true });

  const app = buildApp({ logger: false });
  await app.ready();
  try {
    // 3b. The connection's own answer must match the URL's database name.
    const result = await sql<{ current_database: string }>`select current_database()`.execute(
      app.getDb(),
    );
    const current = result.rows[0]?.current_database;
    if (current !== database) {
      throw new Error(
        `SELECT current_database() returned "${current ?? '(none)'}" but DATABASE_URL names "${database}"; refusing to build.`,
      );
    }
    log(`SELECT current_database() -> "${current}" (matches)`);

    // 3c. An active published run, pinned.
    const pinned = await pinPublishedRun(app);
    log(`active published run pinned: ${shortRunId(pinned.runId)}`);

    // 4. Materialize.
    const materialized = await materializePublicApi(app, pinned.runId, pinned, log);
    for (const [apiPath, raw] of materialized.responses) {
      const file = path.join(SCRATCH_DIR, `${apiPath}.json`);
      mkdirSync(path.dirname(file), { recursive: true });
      writeFileSync(file, raw);
    }
    log(
      `${materialized.responses.size} responses materialized under ${path.relative(REPO_ROOT, SCRATCH_DIR)}/`,
    );

    // 5. Throwaway server + next build.
    const server = await startThrowawayApi(materialized.responses);
    let buildStatus: number | null;
    try {
      log(`throwaway API at ${server.baseUrl}; running next build (output: export)`);
      // Asynchronous spawn, never spawnSync: the throwaway server lives on this
      // process's event loop and must keep answering while next build runs.
      buildStatus = await new Promise<number | null>((resolve, reject) => {
        const child = spawn('pnpm', ['exec', 'next', 'build'], {
          cwd: WEB_DIR,
          stdio: 'inherit',
          env: { ...process.env, PCA_STATIC_EXPORT: '1', API_BASE_URL: server.baseUrl },
        });
        child.once('error', reject);
        child.once('exit', (code) => resolve(code));
      });
    } finally {
      await server.close();
    }
    if (buildStatus !== 0) {
      rmSync(OUT_DIR, { recursive: true, force: true });
      const unserved =
        server.unserved.length > 0
          ? ` (${server.unserved.length} unserved request(s), first: ${server.unserved[0]})`
          : '';
      throw new Error(
        `next build exited with status ${buildStatus ?? 'null'}; export discarded. The throwaway API served ${server.served} request(s)${unserved}.`,
      );
    }
    if (server.unserved.length > 0) {
      rmSync(OUT_DIR, { recursive: true, force: true });
      throw new Error(
        `next build requested ${server.unserved.length} path(s) the materialized set did not have ` +
          `(first: ${server.unserved[0]}); a page may have baked a fallback state — export discarded.`,
      );
    }
    log(`next build done; the throwaway API served ${server.served} requests, 0 unserved`);

    // 6. Data files under the export's top-level data/ (pin 11.6).
    const indexFile = path.join(OUT_DIR, SEARCH_INDEX_DATA_PATH);
    mkdirSync(path.dirname(indexFile), { recursive: true });
    writeFileSync(indexFile, materialized.responses.get('/api/v1/public/search-index') as string);
    let dataFiles = 1;
    for (const [slug, file] of materialized.chargeJudgeFiles) {
      const target = path.join(OUT_DIR, chargeJudgeDataPath(slug));
      mkdirSync(path.dirname(target), { recursive: true });
      writeFileSync(target, JSON.stringify(file));
      dataFiles += 1;
    }

    // 7. Summary, measured — never pinned.
    const files = walk(OUT_DIR);
    let largest = { path: '', bytes: -1 };
    for (const file of files) {
      const bytes = statSync(file).size;
      if (bytes > largest.bytes) largest = { path: path.relative(OUT_DIR, file), bytes };
    }
    const routes = files.filter((f) => f.endsWith('.html')).length;
    return {
      mode,
      database,
      aggregateRunId: pinned.runId,
      routes,
      dataFiles,
      totalFiles: files.length,
      largestFile: largest,
      injected: materialized.counts.injected,
      served: server.served,
    };
  } finally {
    await app.close();
  }
}
