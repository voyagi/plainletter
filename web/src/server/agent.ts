import 'server-only';
import { randomUUID } from 'node:crypto';
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from '@aws-sdk/client-bedrock-agentcore';
import { env } from '@/env';

// Server-only, and the architecture gate enforces it. Everything that reaches the agent goes
// through this module, so the browser never holds a cloud credential: it posts a letter to this
// application's own origin and the signing, the endpoint and the region stay on the server.
//
// Two ways to reach the agent, chosen by configuration. With a runtime ARN set, the request is
// signed with the host's AWS credentials and sent to the deployed AgentCore Runtime. Without one,
// it is a plain POST to the same entrypoint running locally. The payload and the stream that comes
// back are identical, so nothing above this module knows which it was.

export type LetterPayload =
  | { sample: string; visitor_language?: string; consent?: boolean; case_id?: string }
  | {
      letter: { filename: string; text?: string; content_base64?: string };
      visitor_language: string;
      consent?: boolean;
      case_id?: string;
    };

export type AgentAnswer = {
  ok: boolean;
  status: number;
  body: ReadableStream<Uint8Array> | null;
  detail?: string;
};

const RUNTIME_ARN = /^arn:aws:bedrock-agentcore:([a-z0-9-]+):\d{12}:runtime\/[A-Za-z0-9_-]+$/;

export function agentEndpoint(): URL {
  return new URL('/invocations', env.PLAINLETTER_AGENT_ENDPOINT);
}

export function runtimeRegion(arn: string): string {
  const region = RUNTIME_ARN.exec(arn)?.[1];
  if (!region) throw new Error('PLAINLETTER_AGENT_RUNTIME_ARN is not an AgentCore runtime ARN.');
  return region;
}

/** Ask the agent to read one letter and stream its stages back. */
export async function readLetter(
  payload: LetterPayload,
  signal: AbortSignal,
): Promise<AgentAnswer> {
  return ask(JSON.stringify({ ...payload, stream: true }), signal);
}

function ask(body: string, signal: AbortSignal): Promise<AgentAnswer> {
  return env.PLAINLETTER_AGENT_RUNTIME_ARN
    ? invokeRuntime(env.PLAINLETTER_AGENT_RUNTIME_ARN, body, signal)
    : postLocally(body, signal);
}

export type ForgetAnswer = {
  ok: boolean;
  status: number;
  body: unknown;
  detail?: string;
};

/** Ask the agent to erase a case. Not streamed: one question with a number for an answer. */
export async function forgetCase(caseId: string, signal: AbortSignal): Promise<ForgetAnswer> {
  const answer = await ask(JSON.stringify({ forget: caseId }), signal);
  if (!answer.ok || !answer.body) {
    return { ok: false, status: answer.status, body: null, detail: answer.detail };
  }
  const text = await new Response(answer.body).text();
  return { ok: true, status: 200, body: JSON.parse(lastEvent(text) ?? text) };
}

/**
 * The last `data:` line of an event stream, or null when the answer was a plain body.
 *
 * The runtime can answer a non-streaming request over the same event-stream transport, so reading
 * the last data line covers both shapes and needs no second contract with the agent.
 */
function lastEvent(text: string): string | null {
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('data:'));
  const last = lines[lines.length - 1];
  return last ? last.slice('data:'.length).trim() : null;
}

async function invokeRuntime(arn: string, body: string, signal: AbortSignal): Promise<AgentAnswer> {
  const client = new BedrockAgentCoreClient({ region: runtimeRegion(arn) });
  try {
    const answer = await client.send(
      new InvokeAgentRuntimeCommand({
        agentRuntimeArn: arn,
        qualifier: 'DEFAULT',
        // One reading is one runtime session. Continuity between visits is the case id inside
        // the payload, never the runtime session, so nothing about a letter outlives its request.
        runtimeSessionId: `${randomUUID()}-${randomUUID()}`,
        contentType: 'application/json',
        accept: 'text/event-stream',
        payload: new TextEncoder().encode(body),
      }),
      { abortSignal: signal },
    );
    if (!answer.response) {
      return { ok: false, status: 502, body: null, detail: 'The reading service sent nothing.' };
    }
    return { ok: true, status: 200, body: answer.response.transformToWebStream() };
  } catch (failure) {
    return {
      ok: false,
      status: 503,
      body: null,
      detail: `The reading service did not answer (${describe(failure)}).`,
    };
  }
}

async function postLocally(body: string, signal: AbortSignal): Promise<AgentAnswer> {
  let answer: Response;
  try {
    answer = await fetch(agentEndpoint(), {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body,
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
