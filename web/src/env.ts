import { createEnv } from '@t3-oss/env-core';
import { z } from 'zod';

// Imported from the root layout so it runs at boot: a missing or malformed variable throws before
// the console serves anything, rather than deep inside a request that is holding someone's letter.
// runtimeEnv is written out key by key because the bundler only inlines literal process.env reads.
export const env = createEnv({
  server: {
    NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
    PLAINLETTER_AGENT_ENDPOINT: z.url().default('http://127.0.0.1:8080'),
    // The deployed agent. When set, the proxy signs calls to it and the endpoint above is unused.
    PLAINLETTER_AGENT_RUNTIME_ARN: z
      .string()
      .regex(/^arn:aws:bedrock-agentcore:[a-z0-9-]+:\d{12}:runtime\/[A-Za-z0-9_-]+$/)
      .optional(),
    // Set this only when a proxy really does sit in front of this app and append the caller to
    // X-Forwarded-For. Left off, every caller is metered as one, which is stricter rather than
    // looser, and a forgotten setting should fail in that direction.
    PLAINLETTER_TRUST_PROXY_HEADER: z.enum(['true', 'false']).default('false'),
  },
  clientPrefix: 'NEXT_PUBLIC_',
  client: {
    NEXT_PUBLIC_SITE_URL: z.url().default('http://localhost:3000'),
  },
  runtimeEnv: {
    NODE_ENV: process.env.NODE_ENV,
    PLAINLETTER_AGENT_ENDPOINT: process.env.PLAINLETTER_AGENT_ENDPOINT,
    PLAINLETTER_AGENT_RUNTIME_ARN: process.env.PLAINLETTER_AGENT_RUNTIME_ARN,
    PLAINLETTER_TRUST_PROXY_HEADER: process.env.PLAINLETTER_TRUST_PROXY_HEADER,
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL,
  },
  emptyStringAsUndefined: true,
});
