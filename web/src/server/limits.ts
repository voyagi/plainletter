/**
 * What one caller may ask of the reading service, and what all of them together may.
 *
 * IN MEMORY, WHICH IS SAID RATHER THAN HIDDEN. This survives nothing: not a restart, not a second
 * serverless instance. It is the fast guard against one impatient visitor and against a script that
 * found the endpoint, and it is not the budget. The budget is the daily ceiling inside the agent
 * and, above that, the account alarm. Three weak-in-different-ways limits in front of a metered
 * model beat one that reads strong and is not.
 *
 * TWO KEYS, NOT ONE. A help desk is a room of people behind one address, so metering by address
 * alone would let the first visitor of the morning use up the library's day. Metering by a browser
 * marker alone would be worthless, since a caller can throw the marker away and take a fresh one.
 * So both are counted and both must allow: the address ceiling is the one a caller cannot forge,
 * and the per-browser ceiling is what stops one desk from eating the address's whole allowance.
 * Throwing away the marker only ever moves a caller closer to the address ceiling, never past it.
 */

/** Tokens per minute, and readings per UTC day, for one key. */
export interface Ceilings {
  readonly burstPerMinute: number;
  readonly perDay: number;
}

// An address is a building. Thirty readings in a minute is a queue moving fast; a hundred and
// twenty in a day is more letters than a desk sees in a week.
export const ADDRESS_CEILINGS: Ceilings = { burstPerMinute: 30, perDay: 120 };

// A browser is one desk, or one visitor at home. Six in a minute covers a volunteer re-reading a
// letter they photographed badly; twenty-five in a day is a long shift.
export const VISITOR_CEILINGS: Ceilings = { burstPerMinute: 6, perDay: 25 };

// Above this the table is refusing callers it has never seen, which is the fail-closed direction.
// Ten thousand entries is a few megabytes and far more distinct callers than a demo ever has.
export const MAX_TRACKED = 10_000;

const MINUTE_MS = 60_000;
const DAY_MS = 86_400_000;

export interface Caller {
  /** The address the request came from, or a stand-in when there is none to be had. */
  readonly address: string;
  /** The browser marker, which the caller can discard but not use to escape the address. */
  readonly visitor: string;
}

export type Refusal = 'burst' | 'daily' | 'crowd';

export interface Decision {
  readonly allowed: boolean;
  readonly refusedBy: Refusal | null;
  /** What to put in Retry-After. At least 1, because a browser reads 0 as "right now". */
  readonly retryAfterSeconds: number;
}

export interface Limiter {
  take(caller: Caller): Decision;
  /** How many keys are tracked. Read by the test that proves the bound holds. */
  readonly tracked: number;
}

export interface LimiterOptions {
  readonly now?: () => number;
  readonly maxTracked?: number;
}

interface Meter {
  tokens: number;
  lastSeenMs: number;
  day: number;
  usedToday: number;
}

/**
 * Which address to count against.
 *
 * THE LAST hop of `X-Forwarded-For`, never the first. The header is a chain each hop appends to, so
 * the leftmost entry is whatever the caller sent and the rightmost is what the nearest proxy wrote.
 * Trusting the leftmost would hand every caller an endless supply of fresh buckets.
 *
 * And it is read only when the deployment has said a proxy is really in front. With no proxy the
 * header is pure caller input, so honouring it would be the same bypass with more steps. Without
 * one, every caller shares a single address bucket, which is stricter rather than looser, and is
 * the right way for a missing setting to fail.
 */
export function addressOf(headers: Headers, trustProxyHeader: boolean): string {
  if (!trustProxyHeader) return 'untrusted-hop';
  const chain = headers.get('x-forwarded-for');
  const hops = (chain ?? '')
    .split(',')
    .map((hop) => hop.trim())
    .filter((hop) => hop.length > 0);
  return hops[hops.length - 1] ?? headers.get('x-real-ip') ?? 'untrusted-hop';
}

export function createLimiter(options: LimiterOptions = {}): Limiter {
  const now = options.now ?? Date.now;
  const maxTracked = options.maxTracked ?? MAX_TRACKED;
  const meters = new Map<string, Meter>();

  /**
   * Forget only what there is nothing left to remember about.
   *
   * A meter with readings on today's count is never dropped, because dropping it would hand its
   * owner a fresh daily allowance for the price of waiting a minute, which is the whole cap gone.
   * What can go is a meter from an earlier day and a meter whose bucket has refilled with nothing
   * spent, since that is indistinguishable from a caller this table has never seen.
   */
  function sweep(day: number, at: number): void {
    for (const [key, meter] of meters) {
      const idle = at - meter.lastSeenMs >= MINUTE_MS;
      if (meter.day !== day || (idle && meter.usedToday === 0)) meters.delete(key);
    }
  }

  function meterFor(key: string, ceilings: Ceilings, day: number, at: number): Meter | null {
    const existing = meters.get(key);
    if (existing) {
      if (existing.day !== day) {
        existing.day = day;
        existing.usedToday = 0;
      }
      const elapsed = Math.max(0, at - existing.lastSeenMs);
      existing.tokens = Math.min(
        ceilings.burstPerMinute,
        existing.tokens + (elapsed * ceilings.burstPerMinute) / MINUTE_MS,
      );
      existing.lastSeenMs = at;
      return existing;
    }
    if (meters.size >= maxTracked) {
      sweep(day, at);
      if (meters.size >= maxTracked) return null;
    }
    const fresh: Meter = { tokens: ceilings.burstPerMinute, lastSeenMs: at, day, usedToday: 0 };
    meters.set(key, fresh);
    return fresh;
  }

  function refuse(refusedBy: Refusal, seconds: number): Decision {
    return { allowed: false, refusedBy, retryAfterSeconds: Math.max(1, Math.ceil(seconds)) };
  }

  return {
    take(caller: Caller): Decision {
      const at = now();
      const day = Math.floor(at / DAY_MS);
      const pairs: [Meter | null, Ceilings][] = [
        [meterFor(`a:${caller.address}`, ADDRESS_CEILINGS, day, at), ADDRESS_CEILINGS],
        [
          meterFor(`v:${caller.address}|${caller.visitor}`, VISITOR_CEILINGS, day, at),
          VISITOR_CEILINGS,
        ],
      ];

      // Nothing is spent until both ceilings have agreed, so a caller refused by the daily count
      // does not also lose a token from a bucket that was allowing them.
      for (const [meter, ceilings] of pairs) {
        if (!meter) return refuse('crowd', MINUTE_MS / 1000);
        if (meter.usedToday >= ceilings.perDay) {
          return refuse('daily', (DAY_MS - (at % DAY_MS)) / 1000);
        }
        if (meter.tokens < 1) {
          return refuse('burst', ((1 - meter.tokens) * MINUTE_MS) / ceilings.burstPerMinute / 1000);
        }
      }

      for (const [meter] of pairs) {
        if (!meter) continue;
        meter.tokens -= 1;
        meter.usedToday += 1;
      }
      return { allowed: true, refusedBy: null, retryAfterSeconds: 0 };
    },

    get tracked(): number {
      return meters.size;
    },
  };
}
