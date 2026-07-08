# @pca/api

Fastify API shell for Philadelphia Court Outcomes Analytics. This is a shell only — no
database and no real endpoints yet. It provides `GET /health`, request-ID handling, a
central error handler, and the empty `/api/v1/public` and `/api/v1/admin` namespaces.

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

No configuration is required. Environment variables (all optional):

| Variable    | Default     | Purpose        |
| ----------- | ----------- | -------------- |
| `PORT`      | `3001`      | Listen port    |
| `HOST`      | `127.0.0.1` | Listen host    |
| `LOG_LEVEL` | `info`      | Pino log level |

## Error shape

All errors (including 404s and validation failures) share one body:

```json
{ "statusCode": 404, "error": "Not Found", "message": "...", "requestId": "..." }
```

Responses with status ≥ 500 always carry a generic message; details go to logs only.
Every response includes an `x-request-id` header — honored from the request if provided,
generated otherwise.
