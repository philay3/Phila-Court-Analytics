import { createDb } from '../src/connection.js';
import { describeError } from '../src/errors.js';
import { seedAggregates } from './aggregates.js';
import { seedChargeRoster } from './charge-roster.js';
import { seedJudgeRoster } from './judge-roster.js';
import { seedReference } from './reference.js';

async function main(): Promise<void> {
  const db = createDb();
  try {
    // Reference seeds first: aggregate seeds resolve charge/judge ids by slug.
    const referenceResults = await seedReference(db);
    for (const { seed, upserted } of referenceResults) {
      console.log(`seeded ${seed}: ${upserted} row(s) upserted`);
    }
    // Real charge roster (Task 22.2): coexists in ref.* with the demo rows.
    const rosterResults = await seedChargeRoster(db);
    for (const { seed, upserted } of rosterResults) {
      console.log(`seeded ${seed}: ${upserted} row(s) upserted`);
    }
    // Real judge roster (Task 22.3): coexists in ref.* with the fake judges.
    const judgeRosterResults = await seedJudgeRoster(db);
    for (const { seed, upserted } of judgeRosterResults) {
      console.log(`seeded ${seed}: ${upserted} row(s) upserted`);
    }
    const aggregateResults = await seedAggregates(db);
    for (const { run, runId, runRowChanged, tables } of aggregateResults) {
      console.log(
        `aggregate run "${run}" (${runId}): run row ${runRowChanged ? 'upserted' : 'unchanged'}`,
      );
      for (const { table, deleted, inserted } of tables) {
        console.log(`  ${table}: ${deleted} row(s) deleted, ${inserted} row(s) inserted`);
      }
    }
  } finally {
    await db.destroy();
  }
}

main().catch((error: unknown) => {
  const message = describeError(error);
  console.error(`Seed runner failed: ${message}`);
  if (message.includes('ECONNREFUSED')) {
    console.error('Is Postgres running? Start it with: pnpm db:up');
  }
  process.exitCode = 1;
});
