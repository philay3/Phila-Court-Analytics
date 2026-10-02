/**
 * Copy of apps/web/app/lib/api-base-url.ts for the ops workspace (task
 * STATIC-2a): apps share no code, so the resolver is duplicated rather than
 * imported. Behavior is identical, including the NODE_ENV=production throw —
 * inert here because this app only ever runs under `next dev`.
 */
export const LOCAL_DEV_API_BASE_URL = 'http://localhost:3001';

export function resolveApiBaseUrl(apiBaseUrl = process.env.API_BASE_URL): string {
  if (apiBaseUrl !== undefined && apiBaseUrl.length > 0) {
    return apiBaseUrl;
  }
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'API_BASE_URL is required in production and was unset or empty. Set it to ' +
        'the API service address (the internal API hostname in the deployed ' +
        'topology). The http://localhost:3001 fallback is local-dev only and is ' +
        'deliberately disabled here so a misconfiguration fails at build/boot ' +
        'instead of silently pointing at localhost.',
    );
  }
  return LOCAL_DEV_API_BASE_URL;
}
