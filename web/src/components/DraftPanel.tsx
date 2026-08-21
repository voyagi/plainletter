'use client';

import { useState } from 'react';
import { VisitorText } from '@/components/Bilingual';
import type { DraftLetter } from '@/lib/reading';

// The reply the desk would send, in Dutch with the translation beside it, editable because the
// visitor knows things the letter does not say. When no letter is needed the space says so rather
// than disappearing, so nobody wonders whether the desk forgot.

const KIND_NL: Record<DraftLetter['kind'], string> = {
  objection: 'Concept bezwaar',
  payment_plan: 'Concept verzoek betalingsregeling',
  reply: 'Concept antwoord',
};

export function DraftPanel({
  draft,
  language,
  sendBefore,
}: {
  draft: DraftLetter | null;
  language: string;
  sendBefore: string | null;
}) {
  // The volunteer's edits belong to the draft they were typed into. A new letter is a new draft, so
  // the box resets with it rather than carrying the previous visitor's sentences into this one.
  const [source, setSource] = useState(draft);
  const [dutch, setDutch] = useState(draft?.dutch ?? '');
  if (draft !== source) {
    setSource(draft);
    setDutch(draft?.dutch ?? '');
  }

  if (draft === null) {
    return (
      <div className="mt-6 rounded-[10px] bg-paper px-6 py-5 shadow-sheet">
        <p className="m-0 text-[15px] text-ink-2">
          Deze brief vraagt niet om een antwoord. Betaal of handel volgens de stappen hierboven.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-[10px] bg-paper px-6 py-5 shadow-sheet">
      <div className="mb-3.5 flex flex-wrap items-baseline justify-between gap-3.5 border-b border-rule pb-3">
        <span className="text-xs font-bold tracking-[0.12em] text-ink-3 uppercase">
          {KIND_NL[draft.kind]}
        </span>
        <span className="text-xs tracking-[0.12em] text-ink-3 uppercase">
          {draft.addressed_to}
          {sendBefore ? ` · post voor ${sendBefore}` : ''}
        </span>
      </div>

      <label className="block">
        <span className="sr-only">Concept in het Nederlands, aanpasbaar</span>
        <textarea
          lang="nl"
          value={dutch}
          onChange={(event) => setDutch(event.target.value)}
          rows={Math.max(6, dutch.split('\n').length + 1)}
          className="w-full resize-y rounded-lg border border-rule bg-paper px-4 py-3 font-reading text-[14.5px] leading-[1.55] text-ink"
        />
      </label>

      <VisitorText
        language={language}
        className="mt-3 rounded-lg border border-rule px-4 py-3 text-[14.5px] whitespace-pre-line"
      >
        {draft.visitor}
      </VisitorText>
      <p className="mt-3 mb-0 text-[13px] text-ink-2">
        De vertaling laat de bezoeker meelezen. Wat verstuurd wordt is de Nederlandse tekst.
      </p>
    </div>
  );
}
