import { readLetter, type LetterPayload } from '@/server/agent';

// The one door between the browser and the agent. It runs on Node rather than at the edge because
// the deployment phase signs these requests, and the signing needs Node's crypto.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// A letter is a page or a few. Anything past this is refused here as well as in the agent, because
// a browser should not spend a minute uploading something that will be rejected on arrival.
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

const TEXT_TYPES = new Set(['text/plain', 'text/markdown', '']);

export async function POST(request: Request): Promise<Response> {
  let payload: LetterPayload;
  try {
    payload = await intake(request);
  } catch (refusal) {
    return problem(refusal instanceof Error ? refusal.message : 'That upload was not readable.');
  }

  const answer = await readLetter(payload, request.signal);
  if (!answer.ok || !answer.body) {
    return problem(answer.detail ?? 'The reading service did not answer.', answer.status);
  }

  return new Response(answer.body, {
    headers: {
      'content-type': 'text/event-stream; charset=utf-8',
      'cache-control': 'no-store, no-transform',
      connection: 'keep-alive',
    },
  });
}

async function intake(request: Request): Promise<LetterPayload> {
  const type = request.headers.get('content-type') ?? '';
  if (type.includes('application/json')) {
    const body: unknown = await request.json();
    const sample = readString(body, 'sample');
    if (!sample) throw new Error('Send a letter or name a sample letter.');
    return { sample, visitor_language: readString(body, 'visitor_language') ?? undefined };
  }

  const form = await request.formData();
  const file = form.get('letter');
  const language = String(form.get('visitor_language') ?? 'en');
  if (!(file instanceof File) || file.size === 0) {
    throw new Error('Choose a letter first, or take a photo of one.');
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error('That file is too large to be a letter. Send the pages one at a time.');
  }

  const bytes = new Uint8Array(await file.arrayBuffer());
  const filename = file.name || 'letter';
  if (TEXT_TYPES.has(file.type) && filename.endsWith('.txt')) {
    return { letter: { filename, text: new TextDecoder().decode(bytes) }, visitor_language: language };
  }
  return {
    letter: { filename, content_base64: Buffer.from(bytes).toString('base64') },
    visitor_language: language,
  };
}

function readString(body: unknown, key: string): string | null {
  if (typeof body !== 'object' || body === null) return null;
  const value = (body as Record<string, unknown>)[key];
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function problem(detail: string, status = 400): Response {
  return Response.json({ error: { kind: 'upload', detail } }, { status });
}
