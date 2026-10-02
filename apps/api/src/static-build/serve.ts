import { createServer, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';

/**
 * The throwaway API (task STATIC-2b, pin 11.5): serves the materialized
 * responses — byte-identical API bodies — at their exact paths for the
 * duration of `next build`, then stops. It answers nothing else: an unknown
 * path gets the catalog 404 envelope AND is recorded, so the build script can
 * fail closed afterwards (a page that fetched something not materialized can
 * never bake a fallback state unnoticed).
 */
export interface ThrowawayApi {
  baseUrl: string;
  /** Requests answered from the materialized set. */
  served: number;
  /** `METHOD path` of every request that was not in the materialized set. */
  unserved: string[];
  close(): Promise<void>;
}

const NOT_FOUND_BODY = JSON.stringify({
  statusCode: 404,
  code: 'NOT_FOUND',
  error: 'Not Found',
  message: 'Not materialized by the static build.',
  requestId: 'static-build',
});

export function startThrowawayApi(responses: ReadonlyMap<string, string>): Promise<ThrowawayApi> {
  const state = { served: 0, unserved: [] as string[] };
  const debug = process.env.STATIC_BUILD_DEBUG === '1';
  const server: Server = createServer((req, res) => {
    const pathname = new URL(req.url ?? '/', 'http://127.0.0.1').pathname;
    const body = req.method === 'GET' ? responses.get(pathname) : undefined;
    if (debug) {
      console.error(
        `throwaway-api: ${req.method ?? '?'} ${req.url ?? '?'} -> ${body === undefined ? 404 : 200}`,
      );
    }
    if (body === undefined) {
      state.unserved.push(`${req.method ?? '?'} ${req.url ?? '?'}`);
      res.writeHead(404, { 'content-type': 'application/json; charset=utf-8' });
      res.end(NOT_FOUND_BODY);
      return;
    }
    state.served += 1;
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
    res.end(body);
  });

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address() as AddressInfo;
      resolve({
        baseUrl: `http://127.0.0.1:${port}`,
        get served() {
          return state.served;
        },
        get unserved() {
          return state.unserved;
        },
        close: () =>
          new Promise<void>((done, fail) => server.close((err) => (err ? fail(err) : done()))),
      });
    });
  });
}
