import { Type, type Static } from '@sinclair/typebox';

// Plain-English category definitions served by GET /public/definitions,
// sourced from the @pca/taxonomy generated artifact. The entry shape is
// presentation-only: the taxonomy's internal `public` flag is deliberately
// absent so serialization strips it and validation rejects it.
export const definitionEntrySchema = Type.Object(
  {
    code: Type.String(),
    displayName: Type.String(),
    definition: Type.String(),
    sortOrder: Type.Integer(),
  },
  { additionalProperties: false },
);
export type DefinitionEntry = Static<typeof definitionEntrySchema>;

export const definitionsResponseSchema = Type.Object(
  {
    taxonomyVersion: Type.String(),
    outcomes: Type.Array(definitionEntrySchema),
    sentencing: Type.Array(definitionEntrySchema),
  },
  { additionalProperties: false },
);
export type DefinitionsResponse = Static<typeof definitionsResponseSchema>;
