import { createDb } from '../src/connection.js';
import { describeError } from '../src/errors.js';
import { seedReference } from './reference.js';

async function main(): Promise<void> {
  const db = createDb();
  try {
    const results = await seedReference(db);
    for (const { seed, upserted } of results) {
      console.log(`seeded ${seed}: ${upserted} row(s) upserted`);
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
