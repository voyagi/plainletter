import { forgetCase } from '@/server/agent';
import { admit, refusal, withMarker } from '@/server/caller';

// Taking consent back has to be as easy as giving it, so this is the reading door with everything
// a reading needs taken out: no upload, no letter, no model. The case number printed on the desk
// card is the whole request.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const CASE_ID = /^[A-Z0-9]{4}-[A-Z0-9]{4}$/;

export async function POST(request: Request): Promise<Response> {
  // Metered on the same buckets as a reading, because a case number is eight characters and
  // guessing at one is the reason to count these at all.
  const admission = admit(request);
  if (admission.refused) return admission.refused;
  const marker = admission.marker;

  const caseId = caseIdIn(await request.json().catch(() => null));
  if (!CASE_ID.test(caseId)) {
    return refusal(
      'A case number has the shape on the card: four characters, a hyphen, four more.',
      400,
      marker,
    );
  }

  const answer = await forgetCase(caseId, request.signal);
  if (!answer.ok) {
    return refusal(answer.detail ?? 'The reading service did not answer.', answer.status, marker);
  }
  return Response.json(answer.body, { headers: withMarker({}, marker) });
}

function caseIdIn(body: unknown): string {
  if (typeof body !== 'object' || body === null) return '';
  const value = (body as Record<string, unknown>).case_id;
  return typeof value === 'string' ? value.trim().toUpperCase() : '';
}

