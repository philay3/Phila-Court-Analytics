export interface Env {
  port: number;
  host: string;
  logLevel: string;
}

export function loadEnv(): Env {
  const port = Number(process.env.PORT ?? 3000);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new Error(`Invalid PORT: ${process.env.PORT}`);
  }
  return {
    port,
    host: process.env.HOST ?? '127.0.0.1',
    logLevel: process.env.LOG_LEVEL ?? 'info',
  };
}
