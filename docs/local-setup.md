# Local setup

How to run the local development infrastructure. Right now that is a single
PostgreSQL instance via Docker Compose; the API does not connect to it yet
(that arrives with the Kysely work in later tasks).

An object storage emulator is deliberately not included yet; it is deferred
until the pipeline needs one (backlog FDN-002.1, "documented" option).

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed
  and **running**
- Node 22 and pnpm (see the root `README.md`)

## First run

1. Copy the example environment file:

   ```sh
   cp .env.example .env
   ```

   The defaults work as-is for local development. If you edit any of the
   discrete `POSTGRES_*` variables, keep `DATABASE_URL` in sync with them —
   nothing recomposes it for you.

2. Start PostgreSQL:

   ```sh
   pnpm db:up
   ```

## Start / stop / reset

| Command         | Effect                                                  |
| --------------- | ------------------------------------------------------- |
| `pnpm db:up`    | Start PostgreSQL in the background                      |
| `pnpm db:down`  | Stop and remove the container (data is kept)            |
| `pnpm db:logs`  | Follow the PostgreSQL logs                              |
| `pnpm db:reset` | Stop and **delete all data** (removes the named volume) |

Data lives in the named Docker volume `pca_postgres-data`, so it survives
`pnpm db:down` / `pnpm db:up` cycles. Only `pnpm db:reset` clears it.

There is no restart policy: the container does not come back on its own after
a stop or a Docker/machine restart. `pnpm db:up` is always the way to start it.

## Verifying the database is healthy

Check the container status:

```sh
docker compose ps
```

The `postgres` service should show `Up ... (healthy)` within a few seconds of
starting. You can also probe it directly:

```sh
docker compose exec postgres pg_isready -U pca -d pca
```

which should print `... accepting connections`, or open a SQL shell with:

```sh
docker compose exec postgres psql -U pca -d pca
```

## Notes

- Postgres listens on host port **5433** (not the default 5432) to avoid
  colliding with any Postgres already installed on your machine. Override via
  `POSTGRES_PORT` in `.env` if needed.
- `.env` is gitignored; only `.env.example` (placeholder values) is committed.
