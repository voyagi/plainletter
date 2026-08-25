import { describe, expect, it } from 'vitest';
import {
  ADDRESS_CEILINGS,
  VISITOR_CEILINGS,
  addressOf,
  createLimiter,
  type Caller,
} from './limits';

const CALLER: Caller = { address: '203.0.113.7', visitor: 'desk-1' };

function clock(start = 1_756_000_000_000) {
  let at = start;
  return {
    now: () => at,
    advance(ms: number) {
      at += ms;
    },
  };
}

function take(limiter: ReturnType<typeof createLimiter>, caller: Caller, times: number) {
  const decisions = [];
  for (let index = 0; index < times; index += 1) decisions.push(limiter.take(caller));
  return decisions;
}

describe('addressOf', () => {
  it('reads the last hop, which is the one the caller could not have written', () => {
    const headers = new Headers({ 'x-forwarded-for': '10.0.0.1, 198.51.100.9, 203.0.113.7' });
    expect(addressOf(headers, true)).toBe('203.0.113.7');
  });

  it('ignores the header entirely when no proxy is trusted', () => {
    const headers = new Headers({ 'x-forwarded-for': 'anything-i-like' });
    expect(addressOf(headers, false)).toBe('untrusted-hop');
  });

  it('falls back to one shared bucket when there is no chain at all', () => {
    expect(addressOf(new Headers(), true)).toBe('untrusted-hop');
  });
});

describe('createLimiter', () => {
  it('allows a burst up to the visitor ceiling and refuses the next one', () => {
    const time = clock();
    const limiter = createLimiter({ now: time.now });

    const decisions = take(limiter, CALLER, VISITOR_CEILINGS.burstPerMinute + 1);

    expect(decisions.slice(0, -1).every((decision) => decision.allowed)).toBe(true);
    const last = decisions[decisions.length - 1];
    expect(last?.allowed).toBe(false);
    expect(last?.refusedBy).toBe('burst');
    expect(last?.retryAfterSeconds).toBeGreaterThan(0);
  });

  it('refills the bucket as time passes', () => {
    const time = clock();
    const limiter = createLimiter({ now: time.now });
    take(limiter, CALLER, VISITOR_CEILINGS.burstPerMinute);

    expect(limiter.take(CALLER).allowed).toBe(false);
    time.advance(60_000);
    expect(limiter.take(CALLER).allowed).toBe(true);
  });

  it('holds the daily count even when the caller waits between readings', () => {
    const time = clock();
    const limiter = createLimiter({ now: time.now });

    for (let index = 0; index < VISITOR_CEILINGS.perDay; index += 1) {
      expect(limiter.take(CALLER).allowed).toBe(true);
      time.advance(60_000);
    }
    const refused = limiter.take(CALLER);

    expect(refused.allowed).toBe(false);
    expect(refused.refusedBy).toBe('daily');
  });

  it('starts the daily count again on the next day', () => {
    const time = clock();
    const limiter = createLimiter({ now: time.now });
    for (let index = 0; index < VISITOR_CEILINGS.perDay; index += 1) {
      limiter.take(CALLER);
      time.advance(60_000);
    }

    expect(limiter.take(CALLER).allowed).toBe(false);
    time.advance(86_400_000);
    expect(limiter.take(CALLER).allowed).toBe(true);
  });

  it('binds a caller who keeps taking a fresh browser marker to the address ceiling', () => {
    const time = clock();
    const limiter = createLimiter({ now: time.now });
    let allowed = 0;

    // A new marker every time, so every visitor bucket is full. Only the address ceiling is left.
    for (let index = 0; index < ADDRESS_CEILINGS.perDay + 10; index += 1) {
      if (limiter.take({ address: CALLER.address, visitor: `minted-${index}` }).allowed) {
        allowed += 1;
      }
      time.advance(60_000);
    }

    expect(allowed).toBe(ADDRESS_CEILINGS.perDay);
  });

  it('does not let one desk use up the whole building', () => {
    const time = clock();
    const limiter = createLimiter({ now: time.now });

    for (let index = 0; index < VISITOR_CEILINGS.perDay; index += 1) {
      limiter.take({ address: CALLER.address, visitor: 'desk-1' });
      time.advance(60_000);
    }

    expect(limiter.take({ address: CALLER.address, visitor: 'desk-1' }).allowed).toBe(false);
    expect(limiter.take({ address: CALLER.address, visitor: 'desk-2' }).allowed).toBe(true);
  });

  it('refuses an unknown caller rather than growing without a bound', () => {
    const time = clock();
    const limiter = createLimiter({ now: time.now, maxTracked: 4 });

    for (let index = 0; index < 10; index += 1) {
      limiter.take({ address: `198.51.100.${index}`, visitor: `desk-${index}` });
    }
    const decision = limiter.take({ address: '203.0.113.99', visitor: 'desk-new' });

    expect(limiter.tracked).toBeLessThanOrEqual(4);
    expect(decision.allowed).toBe(false);
    expect(decision.refusedBy).toBe('crowd');
  });

  it('forgets a caller who spent nothing, and remembers one who did', () => {
    const time = clock();
    const limiter = createLimiter({ now: time.now, maxTracked: 2 });
    limiter.take({ address: 'spender', visitor: 'desk-1' });
    time.advance(120_000);

    // The table is full of the spender's two meters, so a newcomer is refused rather than
    // admitted by evicting a meter that still carries today's count.
    expect(limiter.take({ address: 'newcomer', visitor: 'desk-2' }).refusedBy).toBe('crowd');
  });
});
