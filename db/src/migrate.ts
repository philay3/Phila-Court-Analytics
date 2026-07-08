import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import { FileMigrationProvider, Migrator, type MigrationResultSet } from 'kysely/migration';

import { createDb } from './connection.js';
import { describeError } from './errors.js';

const COMMANDS = ['latest', 'up', 'down', 'status'] as const;
type Command = (typeof COMMANDS)[number];

const migrationFolder = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'migrations');

function isCommand(value: string | undefined): value is Command {
  return COMMANDS.includes(value as Command);
}

function reportResultSet(command: Command, { error, results }: MigrationResultSet): void {
  for (const result of results ?? []) {
    const action = result.direction === 'Up' ? 'applied' : 'reverted';
    if (result.status === 'Success') {
      console.log(`${action} ${result.migrationName}`);
    } else if (result.status === 'Error') {
      console.error(`FAILED ${result.migrationName}`);
    }
  }
  if (error) {
    const failed = results?.find((result) => result.status === 'Error');
    const location = failed ? `migration "${failed.migrationName}"` : 'migration run';
    throw new Error(`${location} failed: ${describeError(error)}`);
  }
  if (!results || results.length === 0) {
    console.log(
      command === 'down' ? 'No executed migrations to revert.' : 'No pending migrations.',
    );
  }
}

async function status(migrator: Migrator): Promise<void> {
  const migrations = await migrator.getMigrations();
  if (migrations.length === 0) {
    console.log('No migrations found.');
    return;
  }
  for (const migration of migrations) {
    if (migration.executedAt) {
      console.log(`executed  ${migration.name}  (${migration.executedAt.toISOString()})`);
    } else {
      console.log(`pending   ${migration.name}`);
    }
  }
}

async function main(): Promise<void> {
  const command = process.argv[2];
  if (!isCommand(command)) {
    throw new Error(`unknown command "${command ?? ''}" — expected one of: ${COMMANDS.join(', ')}`);
  }

  const db = createDb();
  const migrator = new Migrator({
    db,
    provider: new FileMigrationProvider({ fs, path, migrationFolder }),
  });

  try {
    switch (command) {
      case 'status':
        await status(migrator);
        break;
      case 'latest':
        reportResultSet(command, await migrator.migrateToLatest());
        break;
      case 'up':
        reportResultSet(command, await migrator.migrateUp());
        break;
      case 'down':
        reportResultSet(command, await migrator.migrateDown());
        break;
    }
  } finally {
    await db.destroy();
  }
}

main().catch((error: unknown) => {
  const message = describeError(error);
  console.error(`Migration runner failed: ${message}`);
  if (message.includes('ECONNREFUSED')) {
    console.error('Is Postgres running? Start it with: pnpm db:up');
  }
  process.exitCode = 1;
});
