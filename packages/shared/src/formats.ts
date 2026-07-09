import { FormatRegistry } from '@sinclair/typebox';

// TypeBox (0.34) fails CLOSED on `format` constraints it has no registered checker
// for: TypeCompiler/Value validation rejects every value — valid or not — until the
// host registers the format. (Older TypeBox versions ignored unknown formats, the
// task 3.2 finding; either way, no format-carrying schema validates correctly without
// registration.) registerFormats() registers the three formats the public contracts
// use. The API's request path is separate: Fastify's Ajv bundles ajv-formats and
// enforces these formats natively — the checkers below mirror ajv-formats "full"
// semantics (calendar-valid dates, RFC 3339 date-time) so the two paths agree on
// what is valid.

const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const DATE_TIME_PATTERN =
  /^(\d{4}-\d{2}-\d{2})[tT ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:[zZ]|[+-]\d{2}:\d{2})$/;
// ajv-formats' uuid pattern: any version/variant, optional urn:uuid: prefix.
const UUID_PATTERN = /^(?:urn:uuid:)?[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;

const DAYS_IN_MONTH = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function isDate(value: string): boolean {
  const match = DATE_PATTERN.exec(value);
  if (!match) return false;
  const [, yearPart, monthPart, dayPart] = match;
  if (yearPart === undefined || monthPart === undefined || dayPart === undefined) return false;
  const year = Number(yearPart);
  const month = Number(monthPart);
  const day = Number(dayPart);
  if (month < 1 || month > 12) return false;
  const maxDay = month === 2 && isLeapYear(year) ? 29 : (DAYS_IN_MONTH[month] ?? 0);
  return day >= 1 && day <= maxDay;
}

function isDateTime(value: string): boolean {
  const match = DATE_TIME_PATTERN.exec(value);
  if (!match) return false;
  const [, datePart, hourPart, minutePart, secondPart] = match;
  if (
    datePart === undefined ||
    hourPart === undefined ||
    minutePart === undefined ||
    secondPart === undefined
  ) {
    return false;
  }
  if (!isDate(datePart)) return false;
  const hour = Number(hourPart);
  const minute = Number(minutePart);
  const second = Number(secondPart);
  if (hour > 23 || minute > 59) return false;
  // 60 seconds is valid only as the RFC 3339 leap second 23:59:60.
  if (second > 59) return second === 60 && hour === 23 && minute === 59;
  return true;
}

function isUuid(value: string): boolean {
  return UUID_PATTERN.test(value);
}

// Idempotent: each format is registered once; later calls are no-ops that never throw
// and never replace an already-installed checker.
export function registerFormats(): void {
  if (!FormatRegistry.Has('date')) FormatRegistry.Set('date', isDate);
  if (!FormatRegistry.Has('date-time')) FormatRegistry.Set('date-time', isDateTime);
  if (!FormatRegistry.Has('uuid')) FormatRegistry.Set('uuid', isUuid);
}
