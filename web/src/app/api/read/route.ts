import { randomUUID } from 'node:crypto';
import { env } from '@/env';
import { readLetter, type LetterPayload } from '@/server/agent';
import { addressOf, createLimiter } from '@/server/limits';

// The one door between the browser and the agent. It runs on Node rather than at the edge because
// the deployment phase signs these requests, and the signing needs Node's crypto.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// A letter is a page or a few. Anything past this is refused here as well as in the agent, because
// a browser should not spend a minute uploading something that will be rejected on arrival.
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

const TEXT_TYPES = new Set(['text/plain', 'text/markdown', '']);

// The case number as it is printed on the desk card: two groups of four, readable across a counter.
const CASE_ID = /^[A-Z0-9]{4}-[A-Z0-9]{4}$/;

// A random marker, kept for the browser session, so a busy desk is metered as one desk rather than
// as the whole building. It identifies nothing and grants nothing: discarding it only moves a
// caller closer to the address ceiling. It is strictly necessary to keep an unauthenticated,
// metered endpoint standing, which is why it is set without asking.
const DESK_COOKIE = 'pl_desk';
const DESK_IN_COOKIE_HEADER = new RegExp(`(?:^|;\\s*)${DESK_COOKIE}=([A-Za-z0-9-]+)`);

// Module scope, so it lives as long as this instance does. What that is worth, and what it is not,
// is written in server/limits.ts.
const limiter = createLimiter();

export async function POST(request: Request): Promise<Response> {
  if (!sameOrigin(request)) {
    return problem('This endpoint only answers the Plainletter console.', 403);
  }

  const known = request.headers.get('cookie')?.match(DESK_IN_COOKIE_HEADER)?.[1];
  const desk = known ?? randomUUID();
  // Every answer past this point carries the marker, refusals included. A caller who only ever
  // sees refusals would otherwise arrive with no marker every time and be counted as a new desk.
  const marker = known ? null : deskCookie(desk);

  const decision = limiter.take({
    address: addressOf(request.headers, env.PLAINLETTER_TRUST_PROXY_HEADER === 'true'),
    visitor: desk,
  });
  if (!decision.allowed) {
    return refused(decision.refusedBy, decision.retryAfterSeconds, marker);
  }

  let payload: LetterPayload;
  try {
    payload = await intake(request);
  } catch (refusal) {
    return problem(
      refusal instanceof Error ? refusal.message : 'That upload was not readable.',
      400,
      marker,
    );
  }

  const answer = await readLetter(payload, request.signal);
  if (!answer.ok || !answer.body) {
    return problem(answer.detail ?? 'The reading service did not answer.', answer.status, marker);
  }

  return new Response(answer.body, {
    headers: withMarker(
      {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-store, no-transform',
        connection: 'keep-alive',
      },
      marker,
    ),
  });
}

function withMarker(base: Record<string, string>, marker: string | null): Headers {
  const headers = new Headers(base);
  if (marker) headers.append('set-cookie', marker);
  return headers;
}

/**
 * Refuse a request that a browser did not make from this application's own pages.
 *
 * A browser sends Origin on every cross-origin POST and on same-origin fetches, so a request
 * without one is not the console. That refuses curl too, which is the point: this is a metered
 * path into a model, and it exists for the page in front of it.
 */
function sameOrigin(request: Request): boolean {
  const origin = request.headers.get('origin');
  if (!origin) return false;
  try {
    const sent = new URL(origin);
    return sent.host === request.headers.get('host') || sent.origin === siteOrigin();
  } catch {
    return false;
  }
}

function siteOrigin(): string {
  return new URL(env.NEXT_PUBLIC_SITE_URL).origin;
}

function deskCookie(desk: string): string {
  const secure = env.NODE_ENV === 'production' ? '; Secure' : '';
  return `${DESK_COOKIE}=${desk}; Path=/; HttpOnly; SameSite=Lax${secure}`;
}

function refused(kind: string | null, retryAfterSeconds: number, marker: string | null): Response {
  const detail =
    kind === 'daily'
      ? 'This desk has read its letters for today. It starts again tomorrow.'
      : 'That is more letters at once than this desk reads. Wait a moment and try again.';
  return Response.json(
    { error: { kind: 'rate', detail } },
    {
      status: 429,
      headers: withMarker({ 'retry-after': String(retryAfterSeconds) }, marker),
    },
  );
}

async function intake(request: Request): Promise<LetterPayload> {
  const type = request.headers.get('content-type') ?? '';
  if (type.includes('application/json')) {
    const body: unknown = await request.json();
    const sample = readString(body, 'sample');
    if (!sample) throw new Error('Send a letter or name a sample letter.');
    return {
      sample,
      visitor_language: readString(body, 'visitor_language') ?? undefined,
      ...caseFields(readString(body, 'consent') === 'true' || readFlag(body, 'consent'), readString(body, 'case_id')),
    };
  }

  const form = await request.formData();
  const file = form.get('letter');
  const language = String(form.get('visitor_language') ?? 'en');
  const memory = caseFields(form.get('consent') === 'true', stringOrNull(form.get('case_id')));
  if (!(file instanceof File) || file.size === 0) {
    throw new Error('Choose a letter first, or take a photo of one.');
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error('That file is too large to be a letter. Send the pages one at a time.');
  }

  const bytes = new Uint8Array(await file.arrayBuffer());
  const filename = file.name || 'letter';
  if (TEXT_TYPES.has(file.type) && filename.endsWith('.txt')) {
    return {
      letter: { filename, text: new TextDecoder().decode(bytes) },
      visitor_language: language,
      ...memory,
    };
  }
  return {
    letter: { filename, content_base64: Buffer.from(bytes).toString('base64') },
    visitor_language: language,
    ...memory,
  };
}

/** Consent travels only as an explicit true, and a case number only when it has the printed shape. */
function caseFields(consent: boolean, caseId: string | null): { consent?: boolean; case_id?: string } {
  const normalised = caseId?.trim().toUpperCase() ?? '';
  if (normalised && !CASE_ID.test(normalised)) {
    throw new Error('A case number has the shape on the card: four characters, a hyphen, four more.');
  }
  return { ...(consent ? { consent: true } : {}), ...(normalised ? { case_id: normalised } : {}) };
}

function readString(body: unknown, key: string): string | null {
  if (typeof body !== 'object' || body === null) return null;
  const value = (body as Record<string, unknown>)[key];
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function readFlag(body: unknown, key: string): boolean {
  if (typeof body !== 'object' || body === null) return false;
  return (body as Record<string, unknown>)[key] === true;
}

function stringOrNull(value: FormDataEntryValue | null): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function problem(detail: string, status = 400, marker: string | null = null): Response {
  return Response.json({ error: { kind: 'upload', detail } }, { status, headers: withMarker({}, marker) });
}
