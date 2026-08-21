import 'server-only';
import { env } from '@/env';

// Server-only. The console reaches the agent through this module and never from the browser: the
// deployed runtime is called with signed requests, so anything that touches it would drag cloud
// credentials into the client bundle. The architecture gate enforces that separation.
export function agentEndpoint(): URL {
  return new URL('/invocations', env.PLAINLETTER_AGENT_ENDPOINT);
}
