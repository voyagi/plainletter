import { createEnv } from '@t3-oss/env-core';
import { z } from 'zod';

// Imported from the root layout so it runs at boot: a missing or malformed variable throws before
// the console serves anything, rather than deep inside a request that is holding someone's letter.
// runtimeEnv is written out key by key because the bundler only inlines literal process.env reads.
export const env = createEnv({
  server: {
    NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
    PLAINLETTER_AGENT_ENDPOINT: z.url().default('http://127.0.0.1:8080'),
  },
  clientPrefix: 'NEXT_PUBLIC_',
  client: {
    NEXT_PUBLIC_SITE_URL: z.url().default('http://localhost:3000'),
  },
  runtimeEnv: {
    NODE_ENV: process.env.NODE_ENV,
    PLAINLETTER_AGENT_ENDPOINT: process.env.PLAINLETTER_AGENT_ENDPOINT,
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL,
  },
  emptyStringAsUndefined: true,
});
