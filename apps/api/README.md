# @pca/api

Fastify API for Philadelphia Court Outcomes Analytics. It serves the public,
aggregate-only endpoints under `/api/v1/public` (backed by PostgreSQL via Kysely),
plus `GET /health`, request-ID handling, and a central error handler. The
`/api/v1/admin` namespace is still empty.

## Run

From the repo root:

```sh
pnpm install
pnpm --filter @pca/api dev     # watch mode (tsx), serves http://127.0.0.1:3001
pnpm --filter @pca/api test    # Vitest via fastify.inject (no port binding)
pnpm --filter @pca/api build   # tsc → dist/
pnpm --filter @pca/api start   # run built output
```

## Configuration

Environment variables:

| Variable       | Default     | Purpose                                        |
| -------------- | ----------- | ---------------------------------------------- |
| `DATABASE_URL` | —           | PostgreSQL connection string (required for DB) |
| `PORT`         | `3001`      | Listen port                                    |
| `HOST`         | `127.0.0.1` | Listen host                                    |
| `LOG_LEVEL`    | `info`      | Pino log level                                 |

The `dev` and `start` scripts auto-load the repo-root `.env` via
`--env-file-if-exists=../../.env`, so `cp .env.example .env` at the repo root is
enough — no shell exports needed. Variables already set in the shell take
precedence over the `.env` file, and both scripts still run if no `.env` exists.
The server starts without `DATABASE_URL`; the missing configuration surfaces as
a logged 500 on the first request that touches the database.

## Error shape

All errors (including 404s and validation failures) share one body:

```json
{ "statusCode": 404, "error": "Not Found", "message": "...", "requestId": "..." }
```

Responses with status ≥ 500 always carry a generic message; details go to logs only.
Every response includes an `x-request-id` header — honored from the request if provided,
generated otherwise.
