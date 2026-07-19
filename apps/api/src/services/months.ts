import { PUBLIC_ERROR_CODES } from '@pca/shared';
import { publicError } from '../public-error.js';

/**
 * Day→month conversion for the sentencing-index medians (task 35.2, pin 3).
 *
 * Stored medians are numeric(6,1) DAY values (strings via `pg`); the API
 * serves MONTHS only: days ÷ 30 under the 360-day-year convention, at most
 * one decimal, rounded half-up. The arithmetic is decimal-safe by
 * construction — the string is parsed to integer TENTHS of a day and the
 * division-with-rounding happens in integers, so there is no binary-float
 * representation anywhere a tie could drift (0.15 is not representable as a
 * double; 15 is): monthTenths = floor((dayTenths + 15) / 30), exact half-up
 * at the true tie dayTenths ≡ 15 (mod 30). The final ÷10 only builds the
 * wire number for an already-rounded integer.
 *
 * Null passes through (the all-or-none duration trio); a malformed numeric
 * string is an integrity failure, never a silent 0 — same posture as the
 * unknown-category-code rule.
 */

// numeric(6,1) as `pg` renders it: optional single decimal, no exponent/sign.
const NUMERIC_6_1_PATTERN = /^(\d+)(?:\.(\d))?$/;

export function daysToMonths(days: string | null): number | null {
  if (days === null) {
    return null;
  }
  const match = NUMERIC_6_1_PATTERN.exec(days);
  if (!match) {
    throw publicError(
      PUBLIC_ERROR_CODES.INTERNAL_ERROR,
      `sentencing-index median day value is not a non-negative numeric(6,1) string: "${days}"`,
    );
  }
  const [, whole = '', tenth = '0'] = match;
  const dayTenths = Number(whole) * 10 + Number(tenth);
  const monthTenths = Math.floor((dayTenths + 15) / 30);
  return monthTenths / 10;
}
