# apps/web

Next.js (App Router) public web application.

## Local development

```sh
pnpm --filter @pca/web dev   # web on http://localhost:3000
```

The web app talks to the public API (`apps/api`, which runs on
`http://localhost:3001`) over both a browser path (the Next.js rewrite in
`next.config.ts`, same-origin) and a server-side path (server components).

### Environment

`API_BASE_URL` is the base URL of the public API. It is **optional in local
development**: both fetch paths resolve it through a single helper
(`app/lib/api-base-url.ts`) that defaults to `http://localhost:3001` when the
variable is unset, so a fresh clone works with the API on its default port and
no `.env` file.

Set it only when the API lives somewhere else (a different host or port):

```sh
cp .env.example .env   # then edit API_BASE_URL
```

`API_BASE_URL` has no `NEXT_PUBLIC_` prefix, so it is read server-side only and
never enters a client bundle. Production env wiring that removes reliance on the
local-dev default is Sprint 9 launch-readiness scope.
