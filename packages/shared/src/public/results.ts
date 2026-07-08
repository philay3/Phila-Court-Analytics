import { Type, type Static } from '@sinclair/typebox';
import {
  outcomeDistributionSchema,
  sentencingDistributionSchema,
  taxonomyVersionSchema,
} from './common.js';

export const chargeOnlyResultSchema = Type.Object(
  {
    chargeDisplayName: Type.String(),
    geographyLabel: Type.String(),
    outcomes: outcomeDistributionSchema,
    sentencing: Type.Optional(sentencingDistributionSchema),
    taxonomyVersion: taxonomyVersionSchema,
    lastRefreshed: Type.String({ format: 'date-time' }),
  },
  { additionalProperties: false },
);
export type ChargeOnlyResult = Static<typeof chargeOnlyResultSchema>;

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
