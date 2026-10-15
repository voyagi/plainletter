// @vitest-environment node
// The route builds a real Request from a real form, and jsdom's FormData is not the one Node's
// Request knows how to send, so this file runs on Node's own.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UPLOADS_CLOSED } from '@/server/uploads';
import { POST } from './route';

const SITE = 'http://localhost:3000';

// The deployment's settings, held in one object the tests can change between cases. The read route
// asks the uploads module, which reads this at call time, so a case sets the desk and then knocks.
const settings = vi.hoisted(() => ({
  env: {
    NODE_ENV: 'test',
    NEXT_PUBLIC_SITE_URL: 'http://localhost:3000',
    PLAINLETTER_TRUST_PROXY_HEADER: 'false',
    PLAINLETTER_STAFFED_DESK: 'false',
  },
}));
vi.mock('@/env', () => settings);

// The agent itself is replaced: what is under test is what the door lets through to it.
const agent = vi.hoisted(() => ({ readLetter: vi.fn() }));
vi.mock('@/server/agent', () => agent);

function answered() {
  return {
    ok: true,
    status: 200,
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"stage":"done"}\n\n'));
        controller.close();
      },
    }),
  };
}

function upload(): Request {
  const form = new FormData();
  form.set('letter', new File(['Geachte heer, u moet betalen.'], 'brief.txt', { type: 'text/plain' }));
  form.set('visitor_language', 'uk');
  return new Request(`${SITE}/api/read`, { method: 'POST', body: form, headers: { origin: SITE } });
}

function asJson(body: Record<string, unknown>): Request {
  return new Request(`${SITE}/api/read`, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { origin: SITE, 'content-type': 'application/json' },
  });
}

/** The one payload the route handed to the agent, read off the stand-in. */
function forwarded(): Record<string, unknown> {
  expect(agent.readLetter).toHaveBeenCalledTimes(1);
  return agent.readLetter.mock.calls[0]?.[0] as Record<string, unknown>;
}

beforeEach(() => {
  settings.env.PLAINLETTER_STAFFED_DESK = 'false';
  agent.readLetter.mockReset();
  agent.readLetter.mockResolvedValue(answered());
});

describe('a desk with nobody to check the card', () => {
  it('turns an uploaded letter away and never reaches the agent', async () => {
    const answer = await POST(upload());

    expect(answer.status).toBe(403);
    const body = (await answer.json()) as { error: { kind: string; detail: string } };
    expect(body.error).toEqual({ kind: 'desk', detail: UPLOADS_CLOSED });
    expect(agent.readLetter).not.toHaveBeenCalled();
  });

  it('turns the letter away before a byte of it is read', async () => {
    const request = upload();
    await POST(request);
    expect(request.bodyUsed).toBe(false);
  });

  it('still reads a sample letter', async () => {
    const answer = await POST(asJson({ sample: 'cjib-verkeersboete' }));

    expect(answer.status).toBe(200);
    expect(forwarded()).toEqual({ sample: 'cjib-verkeersboete', visitor_language: undefined });
  });

  it('lets no letter through the sample door', async () => {
    // The JSON branch is the one the gate waves through, so it must carry a sample name and
    // nothing else. A letter tucked in beside a sample is dropped, and a letter alone is refused.
    const beside = await POST(
      asJson({ sample: 'cjib-verkeersboete', letter: { filename: 'brief.txt', text: 'x' } }),
    );
    expect(beside.status).toBe(200);
    expect(forwarded()).not.toHaveProperty('letter');

    agent.readLetter.mockClear();
    const alone = await POST(asJson({ letter: { filename: 'brief.txt', text: 'x' } }));
    expect(alone.status).toBe(400);
    expect(agent.readLetter).not.toHaveBeenCalled();
  });
});

describe('a desk where a trained volunteer checks the card', () => {
  it('reads the letter that was brought', async () => {
    settings.env.PLAINLETTER_STAFFED_DESK = 'true';

    const answer = await POST(upload());

    expect(answer.status).toBe(200);
    expect(answer.headers.get('content-type')).toContain('text/event-stream');
    expect(forwarded()).toEqual({
      letter: { filename: 'brief.txt', text: 'Geachte heer, u moet betalen.' },
      visitor_language: 'uk',
    });
  });
});
