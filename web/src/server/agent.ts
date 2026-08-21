import 'server-only';
import { env } from '@/env';

// Server-only, and the architecture gate enforces it. Everything that reaches the agent goes
// through this module, so the browser never holds a cloud credential: it posts a letter to this
// application's own origin and the signing, the endpoint and the region stay on the server.
//
// Today the endpoint is an HTTP address, which covers the agent running locally and the agent
// running behind a gateway. Calling AgentCore Runtime directly with a signed request is the
// deployment phase's job, and it swaps the fetch below without moving this boundary.

export type LetterPayload =
  | { sample: string; visitor_language?: string }
  | { letter: { filename: string; text?: string; content_base64?: string }; visitor_language: string };

export type AgentAnswer = {
  ok: boolean;
  status: number;
  body: ReadableStream<Uint8Array> | null;
  detail?: string;
};

export function agentEndpoint(): URL {
  return new URL('/invocations', env.PLAINLETTER_AGENT_ENDPOINT);
}

/** Ask the agent to read one letter and stream its stages back. */
export async function readLetter(
  payload: LetterPayload,
  signal: AbortSignal,
): Promise<AgentAnswer> {
  let answer: Response;
  try {
    answer = await fetch(agentEndpoint(), {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify({ ...payload, stream: true }),
      signal,
    });
  } catch (failure) {
    return {
      ok: false,
      status: 503,
      body: null,
      detail: `The reading service did not answer (${describe(failure)}).`,
    };
  }

  if (!answer.ok) {
    return {
      ok: false,
      status: answer.status,
      body: null,
      detail: await answer.text().catch(() => 'no detail'),
    };
  }
  return { ok: true, status: answer.status, body: answer.body };
}

function describe(failure: unknown): string {
  return failure instanceof Error ? failure.message : 'unknown error';
}
