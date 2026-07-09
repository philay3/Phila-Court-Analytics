import { Type, type Static } from '@sinclair/typebox';
import {
  outcomeDistributionSchema,
  sentencingDistributionSchema,
  taxonomyVersionSchema,
} from './common.js';

// The charge-only result contract lives in charge-result.ts (task 8.1 pinned
// shape). judgeSpecificResultSchema below is still the task 3.2 sketch; task
// 8.2 will replace it the same way.

export const judgeSpecificResultSchema = Type.Object(
  {
    chargeDisplayName: Type.String(),
    judgeDisplayName: Type.String(),
    judgeOutcomes: outcomeDistributionSchema,
    judgeSentencing: Type.Optional(sentencingDistributionSchema),
    baselineOutcomes: outcomeDistributionSchema,
    baselineSentencing: Type.Optional(sentencingDistributionSchema),
    taxonomyVersion: taxonomyVersionSchema,
    lastRefreshed: Type.String({ format: 'date-time' }),
  },
  { additionalProperties: false },
);
export type JudgeSpecificResult = Static<typeof judgeSpecificResultSchema>;
