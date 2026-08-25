'use client';

import { useRef } from 'react';
import { languageFor, VISITOR_LANGUAGES } from '@/lib/language';

// The empty desk. A letter arrives one of three ways at a real counter: the visitor has it on
// paper and it goes under the camera, they have a file, or the volunteer wants to show someone how
// this works before a real letter is ever handed over.

export type Sample = { id: string; sender: string; type: string; language: string };

export type Memory = { consent: boolean; caseId: string };

export function Intake({
  samples,
  language,
  onLanguage,
  memory,
  onMemory,
  onFile,
  onSample,
  busy,
}: {
  samples: Sample[];
  language: string;
  onLanguage: (code: string) => void;
  memory: Memory;
  onMemory: (memory: Memory) => void;
  onFile: (file: File) => void;
  onSample: (id: string) => void;
  busy: boolean;
}) {
  const chooser = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);

  return (
    <div className="pt-10">
      <h1 className="m-0 max-w-[20ch] font-brand text-[clamp(30px,4vw,44px)] leading-[1.1] font-bold tracking-[-0.03em]">
        Leg de brief onder de camera.
      </h1>
      <p className="mt-4 max-w-[46ch] text-[17px] text-ink-2">
        De balie leest hem terug in het Nederlands en in de taal van de bezoeker, met elke datum en
        elk bedrag gemarkeerd op het papier waar het vandaan komt.
      </p>
      {/* Said before the first letter goes in, not after the reading comes back: the obligation is
          to tell the person at the moment they start dealing with the system. */}
      <p className="mt-3 max-w-[46ch] text-[15px] text-ink-2">
        Het lezen doet een AI-systeem. Elke datum en elk bedrag wordt daarna gecontroleerd tegen de
        brief zelf, en wat niet klopt komt niet op de kaart.
      </p>

      <div className="mt-7 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => camera.current?.click()}
          className="rounded-lg border border-ink bg-ink px-5 py-3 text-[15px] font-bold text-paper disabled:opacity-60"
        >
          Maak een foto
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => chooser.current?.click()}
          className="rounded-lg border border-ink px-5 py-3 text-[15px] font-bold disabled:opacity-60"
        >
          Kies een bestand
        </button>

        <label className="ml-auto flex items-center gap-2 text-sm text-ink-2">
          Taal van de bezoeker
          <select
            value={language}
            onChange={(event) => onLanguage(event.target.value)}
            className="min-h-[44px] rounded-md border border-rule bg-paper px-3 text-sm text-ink"
          >
            {VISITOR_LANGUAGES.map((item) => (
              <option key={item.code} value={item.code}>
                {item.own} ({item.dutch})
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* The question the volunteer asks out loud before anything is kept. It is a ruled line on
          the same surface, not a panel, because it is part of the intake and not a setting. */}
      <div className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-rule pt-4">
        <label className="flex min-h-[44px] items-center gap-2.5 text-sm">
          <input
            type="checkbox"
            checked={memory.consent}
            onChange={(event) => onMemory({ ...memory, consent: event.target.checked })}
            className="size-[18px] accent-ink"
          />
          De bezoeker wil dat de balie deze zaak dertig dagen onthoudt
        </label>
        <label className="flex min-h-[44px] items-center gap-2.5 text-sm text-ink-2">
          Zaaknummer van de vorige kaart
          <input
            type="text"
            value={memory.caseId}
            onChange={(event) => onMemory({ ...memory, caseId: event.target.value.toUpperCase() })}
            inputMode="text"
            autoCapitalize="characters"
            autoComplete="off"
            spellCheck={false}
            maxLength={9}
            pattern="[A-Z0-9]{4}-[A-Z0-9]{4}"
            className="min-h-[44px] w-[11ch] rounded-md border border-rule bg-paper px-3 text-sm tracking-[0.08em] text-ink tabular-nums"
          />
        </label>
      </div>

      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        onChange={(event) => pick(event.target, onFile)}
      />
      <input
        ref={chooser}
        type="file"
        accept="image/*,application/pdf,text/plain"
        className="sr-only"
        onChange={(event) => pick(event.target, onFile)}
      />

      <p className="mt-10 text-xs font-bold tracking-[0.12em] text-ink-2 uppercase">
        Of lees een voorbeeldbrief
      </p>
      {/* A ruled list rather than a grid of cards: this is a page of letters waiting on a counter,
          and each rule is the line between two of them. */}
      <ul className="mt-2 grid list-none grid-cols-2 gap-x-12 p-0 max-[760px]:grid-cols-1">
        {samples.map((sample) => (
          <li key={sample.id} className="border-t border-rule">
            <button
              type="button"
              disabled={busy}
              onClick={() => onSample(sample.id)}
              className="grid w-full grid-cols-[1fr_auto] items-baseline gap-4 py-3 text-left disabled:opacity-60"
            >
              <span>
                <span className="block text-[15px] font-bold">{sample.sender}</span>
                <span className="mt-0.5 block text-[13.5px] text-ink-2">{sample.type}</span>
              </span>
              <span className="text-xs tracking-[0.12em] text-ink-2 uppercase">
                {languageFor(sample.language).dutch}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-4 max-w-[60ch] text-[13px] text-ink-2">
        De voorbeeldbrieven zijn verzonnen. De namen, adressen en nummers erin bestaan niet.
      </p>
    </div>
  );
}

function pick(input: HTMLInputElement, onFile: (file: File) => void) {
  const file = input.files?.[0];
  // The same photo twice in a row has to start a new reading, and it will not fire a change event
  // unless the value is cleared first.
  input.value = '';
  if (file) onFile(file);
}
