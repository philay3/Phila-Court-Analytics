/**
 * Escapes LIKE/ILIKE wildcards (%, _) and the escape character itself so user
 * input always matches literally. Patterns built from the result must be used
 * with `ESCAPE '\'`.
 */
export function escapeLike(input: string): string {
  return input.replace(/[\\%_]/g, (ch) => `\\${ch}`);
}
