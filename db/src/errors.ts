// pg reports "Postgres unreachable" as an AggregateError (one ECONNREFUSED per
// resolved address) whose own message is empty — unwrap it or CLI runners
// (migrations, seeds) would print a blank error.
export function describeError(error: unknown): string {
  if (error instanceof AggregateError && error.errors.length > 0) {
    return [...new Set(error.errors.map(describeError))].join('; ');
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return String(error);
}
