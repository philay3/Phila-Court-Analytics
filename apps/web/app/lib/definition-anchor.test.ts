import { describe, expect, it } from 'vitest';
import { DEFINITIONS_PATH, definitionAnchor, definitionAnchorId } from './definition-anchor.js';

describe('definitionAnchorId', () => {
  it('builds the <kind>-<categoryCode> fragment used as the definitions-page element id', () => {
    expect(definitionAnchorId('outcome', 'guilty_plea')).toBe('outcome-guilty_plea');
    expect(definitionAnchorId('sentencing', 'incarceration')).toBe('sentencing-incarceration');
  });

  it('is the fragment portion of the matching definitionAnchor', () => {
    expect(definitionAnchor('outcome', 'guilty_plea')).toBe(
      `${DEFINITIONS_PATH}#${definitionAnchorId('outcome', 'guilty_plea')}`,
    );
  });
});

describe('definitionAnchor', () => {
  it('builds /definitions#<kind>-<categoryCode> for outcome and sentencing', () => {
    expect(definitionAnchor('outcome', 'guilty_plea')).toBe('/definitions#outcome-guilty_plea');
    expect(definitionAnchor('sentencing', 'incarceration')).toBe(
      '/definitions#sentencing-incarceration',
    );
  });

  it('uses the taxonomy code verbatim so it matches the id 14.1 will emit', () => {
    expect(definitionAnchor('outcome', 'no_further_penalty')).toBe(
      `${DEFINITIONS_PATH}#outcome-no_further_penalty`,
    );
  });
});
