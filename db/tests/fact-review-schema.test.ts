import { randomUUID } from 'node:crypto';

import type { Kysely, Transaction } from 'kysely';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { createDb } from '../src/connection.js';
import type { Database } from '../src/types.js';

// Constraint-violation checks for the task 21.2 tables (fact.* +
// review.queue_items), run inside rolled-back transactions so the live database
// is never mutated (6.1 rolled-back-transaction precedent; mirrors the 21.1
// parsed-schema.test.ts). Each check opens its own transaction, drives inserts
// up to the violating statement (which aborts the transaction), asserts the
// rejection, and rolls back in `finally`.
//
// Requires the local database with migrations applied. Skipped when
// DATABASE_URL is unset so the suite stays runnable without a database.
//
// All values here are synthetic — no real docket numbers, defendant data, or
// file hashes; `test-*` placeholders only.

const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping fact/review-schema constraint tests. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

const IMPORTED_AT = '2026-01-01T00:00:00.000Z';
const PARSED_AT = '2026-01-01T00:00:00.000Z';
const STARTED_AT = '2026-01-01T00:00:00.000Z';

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

function chargeValues(docketId: string, sequence: number) {
  return { docket_id: docketId, sequence };
}

function sentenceValues(chargeId: string, componentOrder: number) {
  return {
    charge_id: chargeId,
    component_order: componentOrder,
    sentence_type: 'Confinement',
    raw_text: 'Confinement',
  };
}

function buildRunValues() {
  return {
    status: 'in_progress' as const,
    parser_version: 2,
    envelope_parser_version: 5,
    taxonomy_version: 'v0-test',
    roster_snapshot_note: null,
    started_at: STARTED_AT,
    completed_at: null,
    counts: null,
  };
}

function outcomeValues(ids: {
  buildRunId: string;
  parsedChargeId: string;
  parsedDocketId: string;
}) {
  return {
    build_run_id: ids.buildRunId,
    parsed_charge_id: ids.parsedChargeId,
    parsed_docket_id: ids.parsedDocketId,
    normalized_charge_id: null,
    outcome_category_code: 'unknown',
    disposition_date: null,
    normalized_judge_id: null,
    judge_attribution_method: null,
    attribution_method: 'charge_row',
    charge_match_method: 'unmatched',
    outcome_match_method: 'exact',
    mvp_eligible: false,
    public_eligible: false,
    judge_specific_eligible: false,
    review_needed: false,
    taxonomy_version: 'v0-test',
  };
}

function sentenceFactValues(ids: {
  buildRunId: string;
  chargeOutcomeId: string;
  parsedSentenceId: string;
}) {
  return {
    build_run_id: ids.buildRunId,
    charge_outcome_id: ids.chargeOutcomeId,
    parsed_sentence_id: ids.parsedSentenceId,
    normalized_charge_id: null,
    sentencing_category_code: 'unknown',
    sentence_date: null,
    min_days: null,
    max_days: null,
    amount_cents: null,
    normalized_judge_id: null,
    judge_attribution_method: null,
    attribution_method: 'charge_component',
    component_match_method: 'exact',
    mvp_eligible: false,
    public_eligible: false,
    judge_specific_eligible: false,
    review_needed: false,
    taxonomy_version: 'v0-test',
  };
}

function queueItemValues(sourceDocumentId: string, dedupKey: string) {
  return {
    item_type: 'unmapped_charge',
    severity: 'high',
    source_document_id: sourceDocumentId,
    parsed_docket_id: null,
    parsed_charge_id: null,
    parsed_sentence_id: null,
    entity_type: null,
    raw_value: null,
    candidate_context: null,
    reason_code: 'unmapped_charge',
    dedup_key: dedupKey,
  };
}

describe.skipIf(!hasDb)('task 21.2 constraint violations (rolled back)', () => {
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

  // Inserts source_document -> docket -> charge, returning their ids plus a
  // fresh build run. `charge_outcomes` inserts need all four.
  async function seedOutcomeParents(trx: Transaction<Database>) {
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
    const charge = await trx
      .insertInto('parsed.charges')
      .values(chargeValues(docket.id, 1))
      .returning('id')
      .executeTakeFirstOrThrow();
    const run = await trx
      .insertInto('fact.fact_build_runs')
      .values(buildRunValues())
      .returning('id')
      .executeTakeFirstOrThrow();
    return { docId: doc.id, docketId: docket.id, chargeId: charge.id, buildRunId: run.id };
  }

  it('rejects a fact.charge_outcomes row with an orphan build_run_id (FK)', async () => {
    await expectViolation(async (trx) => {
      await trx
        .insertInto('fact.charge_outcomes')
        .values(
          outcomeValues({
            buildRunId: randomUUID(),
            parsedChargeId: randomUUID(),
            parsedDocketId: randomUUID(),
          }),
        )
        .execute();
    });
  });

  it('rejects a duplicate fact.charge_outcomes (build_run_id, parsed_charge_id)', async () => {
    await expectViolation(async (trx) => {
      const { docketId, chargeId, buildRunId } = await seedOutcomeParents(trx);
      const values = outcomeValues({
        buildRunId,
        parsedChargeId: chargeId,
        parsedDocketId: docketId,
      });
      await trx.insertInto('fact.charge_outcomes').values(values).execute();
      await trx.insertInto('fact.charge_outcomes').values(values).execute();
    });
  });

  it('rejects a fact.charge_sentences row with an orphan charge_outcome_id (FK)', async () => {
    await expectViolation(async (trx) => {
      await trx
        .insertInto('fact.charge_sentences')
        .values(
          sentenceFactValues({
            buildRunId: randomUUID(),
            chargeOutcomeId: randomUUID(),
            parsedSentenceId: randomUUID(),
          }),
        )
        .execute();
    });
  });

  it('rejects a duplicate fact.charge_sentences (build_run_id, parsed_sentence_id)', async () => {
    await expectViolation(async (trx) => {
      const { docketId, chargeId, buildRunId } = await seedOutcomeParents(trx);
      const outcome = await trx
        .insertInto('fact.charge_outcomes')
        .values(outcomeValues({ buildRunId, parsedChargeId: chargeId, parsedDocketId: docketId }))
        .returning('id')
        .executeTakeFirstOrThrow();
      const sentence = await trx
        .insertInto('parsed.sentences')
        .values(sentenceValues(chargeId, 0))
        .returning('id')
        .executeTakeFirstOrThrow();
      const values = sentenceFactValues({
        buildRunId,
        chargeOutcomeId: outcome.id,
        parsedSentenceId: sentence.id,
      });
      await trx.insertInto('fact.charge_sentences').values(values).execute();
      await trx.insertInto('fact.charge_sentences').values(values).execute();
    });
  });

  it('rejects a review.queue_items row with an orphan source_document_id (FK)', async () => {
    await expectViolation(async (trx) => {
      await trx
        .insertInto('review.queue_items')
        .values(queueItemValues(randomUUID(), `test-dedup-${randomUUID()}`))
        .execute();
    });
  });

  it('rejects a duplicate review.queue_items.dedup_key', async () => {
    await expectViolation(async (trx) => {
      const doc = await trx
        .insertInto('raw.source_documents')
        .values(sourceDocValues(`test-hash-${randomUUID()}`))
        .returning('id')
        .executeTakeFirstOrThrow();
      const dedupKey = `test-dedup-${randomUUID()}`;
      await trx
        .insertInto('review.queue_items')
        .values(queueItemValues(doc.id, dedupKey))
        .execute();
      await trx
        .insertInto('review.queue_items')
        .values(queueItemValues(doc.id, dedupKey))
        .execute();
    });
  });
});
