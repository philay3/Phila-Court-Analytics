import { describe, expect, it } from 'vitest';
import { PUBLIC_ERROR_CODES } from '@pca/shared';
import { daysToMonths } from './months.js';

// Exhaustive unit coverage for the pin-3 conversion: exact half-up at the
// true ties (dayTenths ≡ 15 mod 30), the 360-day-year anchors, the
// numeric(6,1) bounds, null passthrough, and the malformed-string STOP.

describe('daysToMonths', () => {
  it('passes null through (the all-or-none duration trio)', () => {
    expect(daysToMonths(null)).toBeNull();
  });

  it('converts the 360-day-year anchors exactly', () => {
    expect(daysToMonths('30.0')).toBe(1);
    expect(daysToMonths('345.0')).toBe(11.5);
    expect(daysToMonths('690.0')).toBe(23);
    expect(daysToMonths('720.0')).toBe(24);
  });

  it('accepts pg renderings with and without the single decimal', () => {
    expect(daysToMonths('540')).toBe(18);
    expect(daysToMonths('540.0')).toBe(18);
    expect(daysToMonths('540.5')).toBe(18);
  });

  it('rounds half UP at every true tie (x.05 months)', () => {
    // dayTenths ≡ 15 (mod 30): days/30 lands exactly on a half-tenth.
    expect(daysToMonths('1.5')).toBe(0.1); // 0.05 → 0.1
    expect(daysToMonths('4.5')).toBe(0.2); // 0.15 → 0.2 (0.15 is float-unrepresentable)
    expect(daysToMonths('10.5')).toBe(0.4); // 0.35 → 0.4
    expect(daysToMonths('13.5')).toBe(0.5); // 0.45 → 0.5
    expect(daysToMonths('25.5')).toBe(0.9); // 0.85 → 0.9
    expect(daysToMonths('31.5')).toBe(1.1); // 1.05 → 1.1
    expect(daysToMonths('346.5')).toBe(11.6); // 11.55 → 11.6
  });

  it('rounds down just below a tie and up from the tie upward', () => {
    expect(daysToMonths('1.4')).toBe(0); // 0.0466… → 0.0
    expect(daysToMonths('1.6')).toBe(0.1); // 0.0533… → 0.1
    expect(daysToMonths('344.9')).toBe(11.5); // 11.4966… → 11.5
    expect(daysToMonths('345.1')).toBe(11.5); // 11.5033… → 11.5
  });

  it('handles the bounds of numeric(6,1)', () => {
    expect(daysToMonths('0.0')).toBe(0);
    expect(daysToMonths('0.1')).toBe(0);
    expect(daysToMonths('99999.9')).toBe(3333.3);
  });

  it('never serves days: a converted value is the day value ÷ 30, not the day value', () => {
    expect(daysToMonths('345.0')).not.toBe(345);
    expect(daysToMonths('30.0')).not.toBe(30);
  });

  it('throws INTERNAL_ERROR on malformed numeric strings, never a silent value', () => {
    for (const bad of ['', '-1.0', '1.55', '1.', '.5', 'abc', '1e3', 'NaN', '345,0']) {
      let thrown: unknown;
      try {
        daysToMonths(bad);
      } catch (error) {
        thrown = error;
      }
      expect(thrown, `must throw for "${bad}"`).toBeInstanceOf(Error);
      expect((thrown as Error & { code?: string }).code).toBe(PUBLIC_ERROR_CODES.INTERNAL_ERROR);
    }
  });
});
