'use client';

import { useEffect, useRef } from 'react';
import type { DeadlineView, Urgency } from '@/lib/reading';

// One line, in mark ink at full strength: the date, the days left, the last day a posted reply
// still arrives, and the urgency word. Urgency is never the hue on its own. Each state carries its
// own word and its own treatment, because this page ends up on a black and white printer and in
// front of a colour-blind reader, and both have to read it the same way.

const WORD: Record<Urgency, string> = {
  overdue: 'Te laat',
  due_soon: 'Bijna te laat',
  ample: 'Nog tijd',
  unknown: 'Geen datum',
};

const TREATMENT: Record<Urgency, string> = {
  overdue: 'border border-ink line-through decoration-2',
  due_soon:
    'border border-ink [background-image:repeating-linear-gradient(-45deg,var(--color-rule)_0_4px,transparent_4px_10px)]',
  ample: '',
  unknown: '',
};

export function Deadline({ deadline }: { deadline: DeadlineView | null }) {
  if (deadline === null) {
    return (
      <p className="mt-6 border-t-2 border-rule py-3.5 text-[15px] text-ink-2">
        Deze brief noemt geen uiterste datum.
      </p>
    );
  }

  const late = deadline.days_left < 0;
  const days = Math.abs(deadline.days_left);
  return (
    <div className="mt-6 flex flex-wrap items-baseline gap-x-5 gap-y-2 border-t-2 border-b border-t-mark border-b-rule pt-3.5 pb-4">
      <span className="text-[23px] font-bold text-mark">{deadline.on_written}</span>
      <span className="text-[23px] font-bold text-mark">
        {late ? <><Counting to={days} /> dagen te laat</> : <>nog <Counting to={days} /> dagen</>}
      </span>
      {deadline.post_by_written ? (
        <span className="text-[15px] text-ink-2">
          Post een antwoord uiterlijk {deadline.post_by_written}, dan is het op tijd binnen.
        </span>
      ) : null}
      <span
        className={`px-2 pt-[3px] pb-1 text-xs font-bold tracking-[0.1em] uppercase ${TREATMENT[deadline.urgency]}`}
      >
        {WORD[deadline.urgency]}
      </span>
    </div>
  );
}

/**
 * The days-left numeral counts once to its value and settles. No bounce, no loop.
 *
 * The final number is what renders, so the page is correct before a script runs and correct if one
 * never does. The count is an animation written over that number, which is why it lives in the DOM
 * node rather than in state: nothing downstream should re-render because a digit is mid-flight.
 */
function Counting({ to }: { to: number }) {
  const node = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const target = node.current;
    if (!target || to === 0) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const steps = Math.min(to, 20);
    let step = 0;
    target.textContent = '0';
    const timer = window.setInterval(() => {
      step += 1;
      target.textContent = String(Math.round((to * step) / steps));
      if (step >= steps) window.clearInterval(timer);
    }, 22);
    return () => {
      window.clearInterval(timer);
      target.textContent = String(to);
    };
  }, [to]);

  return <span ref={node}>{to}</span>;
}
