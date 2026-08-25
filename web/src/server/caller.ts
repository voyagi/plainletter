import { randomUUID } from 'node:crypto';
import { env } from '@/env';
import { addressOf, createLimiter, type Caller, type Limiter } from './limits';

// Who is at the door, and whether the door opens for them. Both routes into the agent ask the same
// two questions, so they ask them in one place: a second copy of an origin check is a second chance
// to get one of them subtly wrong.

// A random marker, kept for the browser session, so a busy desk is metered as one desk rather than
// as the whole building. It identifies nothing and grants nothing: discarding it only moves a
// caller closer to the address ceiling. It is strictly necessary to keep an unauthenticated,
// metered endpoint standing, which is why it is set without asking.
const DESK_COOKIE = 'pl_desk';
const DESK_IN_COOKIE_HEADER = new RegExp(`(?:^|;\\s*)${DESK_COOKIE}=([A-Za-z0-9-]+)`);

export type Arrival = {
  readonly caller: Caller;
  /** The Set-Cookie value when this caller had no marker yet, and null when they already did. */
  readonly marker: string | null;
};

// One limiter for both routes, so a caller cannot get a fresh allowance by knocking on the other
// door. It lives as long as this instance does, and what that is worth is written in limits.ts.
let shared: Limiter | null = null;

export function deskLimiter(): Limiter {
  shared ??= createLimiter();
  return shared;
}

export type Admission =
  | { readonly refused: Response }
  | { readonly refused: null; readonly marker: string | null };

/**
 * The two questions both doors ask before they do anything: is this the console, and has this
 * caller had their share. A route that answers `refused` returns it and stops.
 */
export function admit(request: Request): Admission {
  if (!fromOwnOrigin(request)) {
    return { refused: refusal('This endpoint only answers the Plainletter console.', 403, null) };
  }
  // Every answer past this point carries the marker, refusals included. A caller who only ever
  // sees refusals would otherwise arrive with no marker every time and be counted as a new desk.
  const { caller, marker } = arrivalFrom(request);
  const decision = deskLimiter().take(caller);
  if (!decision.allowed) {
    const detail =
      decision.refusedBy === 'daily'
        ? 'This desk has read its letters for today. It starts again tomorrow.'
        : 'That is more at once than this desk handles. Wait a moment and try again.';
    return {
      refused: refusal(detail, 429, marker, {
        'retry-after': String(decision.retryAfterSeconds),
      }),
    };
  }
  return { refused: null, marker };
}

export function refusal(
  detail: string,
  status: number,
  marker: string | null,
  extra: Record<string, string> = {},
): Response {
  return Response.json(
    { error: { kind: 'desk', detail } },
    { status, headers: withMarker(extra, marker) },
  );
}

export function arrivalFrom(request: Request): Arrival {
  const known = request.headers.get('cookie')?.match(DESK_IN_COOKIE_HEADER)?.[1];
  const visitor = known ?? randomUUID();
  return {
    caller: {
      address: addressOf(request.headers, env.PLAINLETTER_TRUST_PROXY_HEADER === 'true'),
      visitor,
    },
    marker: known ? null : deskCookie(visitor),
  };
}

/**
 * Refuse a request that a browser did not make from this application's own pages.
 *
 * A browser sends Origin on every cross-origin POST and on same-origin fetches, so a request
 * without one is not the console. That refuses curl too, which is the point: these are metered
 * paths into a model and they exist for the page in front of them.
 */
export function fromOwnOrigin(request: Request): boolean {
  const origin = request.headers.get('origin');
  if (!origin) return false;
  try {
    const sent = new URL(origin);
    const site = new URL(env.NEXT_PUBLIC_SITE_URL).origin;
    return sent.host === request.headers.get('host') || sent.origin === site;
  } catch {
    return false;
  }
}

export function withMarker(base: Record<string, string>, marker: string | null): Headers {
  const headers = new Headers(base);
  if (marker) headers.append('set-cookie', marker);
  return headers;
}

function deskCookie(visitor: string): string {
  const secure = env.NODE_ENV === 'production' ? '; Secure' : '';
  return `${DESK_COOKIE}=${visitor}; Path=/; HttpOnly; SameSite=Lax${secure}`;
}
