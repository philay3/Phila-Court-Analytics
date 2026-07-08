import { FormatRegistry } from '@sinclair/typebox';

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const DATE_TIME_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

// TypeBox only enforces `format` constraints for formats the host application has
// registered. Tests register minimal checkers here; runtime consumers (e.g. the API)
// must register their own (Fastify/Ajv handles this via ajv-formats).
export function registerStringFormats(): void {
  if (!FormatRegistry.Has('date')) {
    FormatRegistry.Set('date', (value) => DATE_PATTERN.test(value));
  }
  if (!FormatRegistry.Has('date-time')) {
    FormatRegistry.Set('date-time', (value) => DATE_TIME_PATTERN.test(value));
  }
}
