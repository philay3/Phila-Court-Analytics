# @pca/ops — operator dashboard (local only)

The Phase 36 ops dashboard, relocated from `apps/web/app/admin` (task STATIC-2a)
so the public web app can be exported as a static site without it. Same
dashboard, same `/admin` URL, same `/admin/numbers` same-origin proxy with the
`x-admin-ops-token` header behavior; only the workspace changed.

**Local only. Never deployed.** There is no build script and no deploy path; the
app runs with `next dev` on the operator's machine against the local canonical
database, through the API.

## Run

1. Start the API with the ops feed enabled (the root `.env` carries
   `ADMIN_OPS_ENABLED=1`; add `ADMIN_OPS_TOKEN` if you want the header check):

   ```sh
   pnpm --filter @pca/api dev        # or `run start` from built dist; port 3001
   ```

2. Start the dashboard on port 3002 (3000/3001 stay free for the public web
   app, the API, and the E2E suite):

   ```sh
   pnpm --filter @pca/ops dev
   ```

3. Open <http://localhost:3002/admin>. Without the API flag the page renders its
   disabled state; with the API down it renders the unreachable state and
   retries on the next poll.

`API_BASE_URL` is optional: `app/lib/api-base-url.ts` (a copy of the web app's
resolver) defaults to `http://localhost:3001` under `next dev`. Set it in
`apps/ops/.env` or the shell only when the API lives elsewhere.

## Checks

```sh
pnpm --filter @pca/ops typecheck   # next typegen + tsc --noEmit
pnpm --filter @pca/ops test        # the dashboard component test (jsdom)
```

Both also run through the root `pnpm typecheck` / `pnpm test` recursion.
