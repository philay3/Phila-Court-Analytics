import { randomUUID } from 'node:crypto';

import type { Kysely, Transaction } from 'kysely';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { createDb } from '../src/connection.js';
import type { Database } from '../src/types.js';

// Constraint-violation checks for the task 21.1 tables (raw.source_documents +
// parsed.*), run inside rolled-back transactions so the live database is never
// mutated (6.1 rolled-back-transaction precedent). Each check opens its own
// transaction, drives inserts up to the violating statement (which aborts the
// transaction), asserts the rejection, and rolls back in `finally`.
//
// Requires the local database with migrations applied. Skipped when
// DATABASE_URL is unset so the suite stays runnable without a database, exactly
// like db/seeds/reference.test.ts.
//
// All values here are synthetic — no real docket numbers, defendant data, or
// file hashes. `parsed.docket_number`/`defendant_hash` use obvious `test-*`
// placeholders.

const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping parsed-schema constraint tests. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

const IMPORTED_AT = '2026-01-01T00:00:00.000Z';
const PARSED_AT = '2026-01-01T00:00:00.000Z';

function sourceDocValues(fileHash: string) {
  return {
    file_hash: fileHash,
    original_filename: 'test-doc.pdf',
    file_size_bytes: 1024,
    imported_at: IMPORTED_AT,
    import_mode: 'manual',
    status: 'imported',
  };
}

function docketValues(sourceDocumentId: string) {
  return {
    source_document_id: sourceDocumentId,
    docket_number: 'test-docket-0001',
    record_parser_version: 2,
    envelope_parser_version: 5,
    parsed_at: PARSED_AT,
    county: 'Philadelphia',
    defendant_hash: 'test-defendant-hash-0001',
    envelope_status: 'parsed',
    review_needed: false,
  };
}

describe.skipIf(!hasDb)('task 21.1 constraint violations (rolled back)', () => {
  let db: Kysely<Database>;

  beforeAll(() => {
    db = createDb();
  });

  afterAll(async () => {
    await db.destroy();
  });

  // Runs `body` inside a transaction, asserts it rejects, always rolls back.
  async function expectViolation(body: (trx: Transaction<Database>) => Promise<unknown>) {
    const trx = await db.startTransaction().execute();
    try {
      await expect(body(trx)).rejects.toThrow();
    } finally {
      await trx.rollback().execute();
    }
  }

  it('rejects a duplicate raw.source_documents.file_hash', async () => {
    const fileHash = `test-hash-${randomUUID()}`;
    await expectViolation(async (trx) => {
      await trx.insertInto('raw.source_documents').values(sourceDocValues(fileHash)).execute();
      await trx.insertInto('raw.source_documents').values(sourceDocValues(fileHash)).execute();
    });
  });

  it('rejects a parsed.dockets row with an orphan source_document_id (FK)', async () => {
    await expectViolation(async (trx) => {
      await trx.insertInto('parsed.dockets').values(docketValues(randomUUID())).execute();
    });
  });

  it('rejects a duplicate parsed.dockets.source_document_id (one docket per source)', async () => {
    await expectViolation(async (trx) => {
      const doc = await trx
        .insertInto('raw.source_documents')
        .values(sourceDocValues(`test-hash-${randomUUID()}`))
        .returning('id')
        .executeTakeFirstOrThrow();
      await trx.insertInto('parsed.dockets').values(docketValues(doc.id)).execute();
      await trx.insertInto('parsed.dockets').values(docketValues(doc.id)).execute();
    });
  });

  it('rejects a parsed.charges row with an orphan docket_id (FK)', async () => {
    await expectViolation(async (trx) => {
      await trx
        .insertInto('parsed.charges')
        .values({ docket_id: randomUUID(), sequence: 1 })
        .execute();
    });
  });

  it('rejects a duplicate parsed.charges (docket_id, sequence)', async () => {
    await expectViolation(async (trx) => {
      const doc = await trx
        .insertInto('raw.source_documents')
        .values(sourceDocValues(`test-hash-${randomUUID()}`))
        .returning('id')
        .executeTakeFirstOrThrow();
      const docket = await trx
        .insertInto('parsed.dockets')
        .values(docketValues(doc.id))
        .returning('id')
        .executeTakeFirstOrThrow();
      await trx
        .insertInto('parsed.charges')
        .values({ docket_id: docket.id, sequence: 1 })
        .execute();
      await trx
        .insertInto('parsed.charges')
        .values({ docket_id: docket.id, sequence: 1 })
        .execute();
    });
  });

  it('rejects a parsed.sentences row with an orphan charge_id (FK)', async () => {
    await expectViolation(async (trx) => {
      await trx
        .insertInto('parsed.sentences')
        .values({
          charge_id: randomUUID(),
          component_order: 0,
          sentence_type: 'Confinement',
          raw_text: 'Confinement',
        })
        .execute();
    });
  });
});
