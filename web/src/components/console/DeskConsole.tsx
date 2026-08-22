'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Deadline } from '@/components/Deadline';
import { DraftPanel } from '@/components/DraftPanel';
import { LetterSheet } from '@/components/LetterSheet';
import { ReadingPanel } from '@/components/ReadingPanel';
import { Sentence } from '@/components/Sentence';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Wordmark } from '@/components/Wordmark';
import { Intake, type Memory, type Sample } from '@/components/console/Intake';
import { languageFor } from '@/lib/language';
import {
  isCase,
  isDone,
  isError,
  isRefusal,
  type CaseInfo,
  type DeskReading,
  type ReadingStage,
} from '@/lib/reading';
import { readMessages } from '@/lib/stream';

// Nothing about this letter is stored. It lives in this tab for as long as a desk conversation
// lasts and then it is gone, which is why the utility line carries a clock rather than a promise.
const HOLD_MINUTES = 15;

type Held = {
  reading: Partial<DeskReading>;
  card: string | null;
  ics: string | null;
  photo: string | null;
  case: CaseInfo | null;
};

const EMPTY: Held = { reading: {}, card: null, ics: null, photo: null, case: null };
const NO_MEMORY: Memory = { consent: false, caseId: '' };

export function DeskConsole({ samples }: { samples: Sample[] }) {
  const [held, setHeld] = useState<Held>(EMPTY);
  const [language, setLanguage] = useState('uk');
  const [memory, setMemory] = useState<Memory>(NO_MEMORY);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [showPhoto, setShowPhoto] = useState(true);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const running = useRef<AbortController | null>(null);

  const clear = useCallback(() => {
    running.current?.abort();
    running.current = null;
    setHeld((previous) => {
      if (previous.photo) URL.revokeObjectURL(previous.photo);
      return EMPTY;
    });
    setSecondsLeft(null);
    setProblem(null);
    setRefusal(null);
    setBusy(false);
    // Consent is given per letter, out loud. It never carries over to the next visitor.
    setMemory(NO_MEMORY);
  }, []);

  useEffect(() => {
    if (secondsLeft === null) return;
    const timer = window.setTimeout(() => {
      if (secondsLeft <= 1) clear();
      else setSecondsLeft(secondsLeft - 1);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [secondsLeft, clear]);

  const read = useCallback(
    async (body: BodyInit, headers: HeadersInit, photo: string | null) => {
      running.current?.abort();
      const controller = new AbortController();
      running.current = controller;
      setBusy(true);
      setProblem(null);
      setRefusal(null);
      setHeld({ ...EMPTY, photo });
      setShowPhoto(photo !== null);
      setSecondsLeft(HOLD_MINUTES * 60);

      try {
        const answer = await fetch('/api/read', {
          method: 'POST',
          body,
          headers,
          signal: controller.signal,
        });
        if (!answer.ok || !answer.body) {
          const detail = await answer.json().catch(() => null);
          throw new Error(detail?.error?.detail ?? `De balie kreeg geen antwoord (${answer.status}).`);
        }
        for await (const message of readMessages(answer.body)) {
          if (isError(message)) throw new Error(message.error.detail);
          if (isRefusal(message)) {
            setRefusal(message.message);
            continue;
          }
          if (isCase(message)) {
            setHeld((previous) => ({ ...previous, case: message.case }));
            continue;
          }
          if (isDone(message)) {
            setHeld((previous) => ({
              ...previous,
              reading: message.reading,
              card: message.desk_card_html,
              ics: message.reminder_ics,
              case: message.case ?? previous.case,
            }));
            continue;
          }
          setHeld((previous) => ({
            ...previous,
            reading: { ...previous.reading, ...withoutStageName(message) },
          }));
        }
      } catch (failure) {
        if (controller.signal.aborted) return;
        setProblem(failure instanceof Error ? failure.message : 'Er ging iets mis.');
      } finally {
        if (running.current === controller) {
          running.current = null;
          setBusy(false);
        }
      }
    },
    [],
  );

  function readFile(file: File) {
    const form = new FormData();
    form.set('letter', file);
    form.set('visitor_language', language);
    if (memory.consent) form.set('consent', 'true');
    if (memory.caseId.trim()) form.set('case_id', memory.caseId.trim());
    void read(form, {}, file.type.startsWith('image/') ? URL.createObjectURL(file) : null);
  }

  function readSample(id: string) {
    void read(
      JSON.stringify({
        sample: id,
        ...(memory.consent ? { consent: true } : {}),
        ...(memory.caseId.trim() ? { case_id: memory.caseId.trim() } : {}),
      }),
      { 'content-type': 'application/json' },
      null,
    );
  }

  const reading = held.reading;
  const started = busy || Object.keys(reading).length > 0 || refusal !== null;
  const visitor = reading.visitor_language ?? language;

  return (
    /* The chrome of this surface is Dutch: it belongs to the volunteer, not to the site around it.
       Saying so here rather than on the document keeps the pronunciation right for a screen reader
       without claiming the landing page is Dutch too. */
    <div lang="nl" className="mx-auto max-w-[1300px] px-7 pb-11">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-rule pt-4 pb-3.5">
        <Wordmark />
        <span className="text-xs tracking-[0.12em] text-ink-2 uppercase">Balie</span>
        <span className="ml-auto flex items-center gap-2.5 text-sm text-ink-2">
          <span lang="nl">Nederlands</span>
          <span aria-hidden>+</span>
          <span lang={visitor} className={languageFor(visitor).script === 'cyrillic' ? 'font-cyrillic' : ''}>
            {languageFor(visitor).own}
          </span>
        </span>
        {secondsLeft !== null ? (
          <span className="text-[13px] text-ink-2" aria-live="off">
            In het geheugen, nog {clock(secondsLeft)}
          </span>
        ) : null}
        <ThemeToggle />
        {started ? (
          <button
            type="button"
            onClick={clear}
            className="min-h-[44px] rounded-md border border-rule px-4 text-sm"
          >
            Brief wissen
          </button>
        ) : null}
      </div>

      {!started ? (
        <Intake
          samples={samples}
          language={language}
          onLanguage={setLanguage}
          memory={memory}
          onMemory={setMemory}
          onFile={readFile}
          onSample={readSample}
          busy={busy}
        />
      ) : (
        <>
          {problem ? <Problem detail={problem} onRetry={clear} /> : null}
          {refusal ? <Refusal message={refusal} /> : null}
          {held.case ? <Case info={held.case} /> : null}

          <Sentence reading={reading} />
          <Deadline deadline={reading.deadline ?? null} />

          <div className="mt-6 grid grid-cols-[47fr_53fr] items-start gap-8 max-[1000px]:grid-cols-1">
            <div>
              <div className="mb-2.5 flex items-baseline justify-between">
                <span className="text-xs tracking-[0.12em] text-ink-2 uppercase">De brief</span>
                {held.photo ? (
                  <button
                    type="button"
                    onClick={() => setShowPhoto(!showPhoto)}
                    className="min-h-[44px] rounded-md border border-rule px-4 text-xs"
                  >
                    {showPhoto ? 'Toon de tekst' : 'Toon de foto'}
                  </button>
                ) : null}
              </div>

              {held.photo && showPhoto ? (
                /* The volunteer's own photograph, held in this tab and never uploaded twice. */
                <img
                  src={held.photo}
                  alt="De foto van de brief zoals die is gemaakt"
                  className="w-full rotate-[-0.35deg] rounded-[10px] shadow-sheet max-[1000px]:rotate-0"
                />
              ) : reading.letter ? (
                <LetterSheet letter={reading.letter} />
              ) : (
                <div className="min-h-[24rem] rounded-[10px] bg-paper px-6 py-7 text-[13.5px] text-ink-2 shadow-sheet">
                  De brief wordt gelezen.
                </div>
              )}

              <DraftPanel
                draft={reading.draft ?? null}
                language={visitor}
                sendBefore={reading.deadline?.post_by_written ?? null}
              />
            </div>

            <div>
              <div className="mb-2.5 flex items-baseline justify-between">
                <span className="text-xs tracking-[0.12em] text-ink-2 uppercase">
                  Wat de balie eruit las
                </span>
                <span className="text-xs tracking-[0.12em] text-ink-2 uppercase">
                  {counted(reading)}
                </span>
              </div>
              <ReadingPanel reading={reading} />
            </div>
          </div>

          <Actions
            card={held.card}
            ics={held.ics}
            reading={reading}
            remembered={held.case?.remembered ?? false}
            onClear={clear}
          />
        </>
      )}
    </div>
  );
}

function Actions({
  card,
  ics,
  reading,
  remembered,
  onClear,
}: {
  card: string | null;
  ics: string | null;
  reading: Partial<DeskReading>;
  remembered: boolean;
  onClear: () => void;
}) {
  const frame = useRef<HTMLIFrameElement>(null);

  function print() {
    const window_ = frame.current?.contentWindow;
    if (!window_) return;
    window_.focus();
    window_.print();
  }

  function save() {
    if (!ics) return;
    const url = URL.createObjectURL(new Blob([ics], { type: 'text/calendar;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${(reading.sender_name ?? 'plainletter').toLowerCase().replace(/\W+/g, '-')}.ics`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mt-7 flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={print}
        disabled={!card}
        className="rounded-lg border border-ink bg-ink px-5 py-3 text-[15px] font-bold text-paper disabled:opacity-60"
      >
        Print de kaart
      </button>
      <button
        type="button"
        onClick={save}
        disabled={!ics}
        className="rounded-lg border border-ink px-5 py-3 text-[15px] font-bold disabled:opacity-60"
      >
        Zet de herinnering klaar
      </button>
      <button
        type="button"
        onClick={onClear}
        className="rounded-lg border border-ink px-5 py-3 text-[15px] font-bold"
      >
        Nieuwe brief
      </button>
      <span className="ml-auto max-w-[340px] text-[13px] text-ink-2">
        {remembered
          ? 'Alleen de gecontroleerde feiten zijn bewaard, dertig dagen, onder het zaaknummer op de kaart. De brief zelf niet.'
          : 'Niets van deze brief wordt bewaard. Wil de bezoeker een volgende keer verder waar hij nu stopt, dan vraagt de balie daar eerst toestemming voor.'}
      </span>
      {/* The card the printer gets is the one the agent rendered, byte for byte. Rebuilding it here
          would put a second version of the visitor's deadline on the paper they take home. */}
      {card ? (
        <iframe
          ref={frame}
          title="De baliekaart, klaar om te printen"
          srcDoc={card}
          className="sr-only"
          tabIndex={-1}
          aria-hidden
        />
      ) : null}
    </div>
  );
}

function Problem({ detail, onRetry }: { detail: string; onRetry: () => void }) {
  return (
    <div className="mt-6 rounded-[10px] bg-paper px-6 py-5 shadow-sheet" role="alert">
      <p className="m-0 text-[17px] font-bold">De brief is niet gelezen.</p>
      <p className="mt-1.5 mb-0 text-[15px] text-ink-2">{detail}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-lg border border-ink px-4 py-2 text-sm font-bold"
      >
        Opnieuw beginnen
      </button>
    </div>
  );
}

/**
 * The case line: what the desk kept, or what it found from last time. Ink only, one ruled line,
 * because a remembered case is a fact about this visit and not a feature to be sold.
 */
function Case({ info }: { info: CaseInfo }) {
  const earlier = info.earlier;
  return (
    <div className="mt-6 border-y border-rule py-3 text-[15px]" aria-live="polite">
      {earlier.length > 0 ? (
        <p className="m-0">
          <span className="text-xs tracking-[0.12em] text-ink-2 uppercase">Eerder aan de balie</span>
          <span className="ml-3">
            {earlier.map((record, index) => (
              <span key={`${record.read_on}-${index}`}>
                {index > 0 ? ', ' : ''}
                <b>{record.sender_name}</b>, {record.letter_type}, gelezen op {record.read_on}
                {record.deadline ? `, uiterlijk ${record.deadline}` : ''}
              </span>
            ))}
          </span>
        </p>
      ) : null}
      {info.remembered && info.id ? (
        <p className={`m-0 ${earlier.length > 0 ? 'mt-1.5' : ''}`}>
          Deze zaak is dertig dagen bewaard onder nummer{' '}
          <b className="tracking-[0.08em] tabular-nums">{info.id}</b>. Het staat op de kaart.
        </p>
      ) : null}
      {info.note ? (
        <p className="m-0 mt-1.5 text-ink-2">
          Deze balie bewaart geen zaken: er is geen geheugen aan gekoppeld. De toestemming is
          genoteerd, er is niets opgeslagen.
        </p>
      ) : null}
    </div>
  );
}

function Refusal({ message }: { message: string }) {
  return (
    <div className="mt-6 rounded-[10px] bg-paper px-6 py-5 shadow-sheet" role="alert">
      <p className="m-0 text-[17px] font-bold text-mark">De balie weigert deze lezing.</p>
      <p className="mt-1.5 mb-0 max-w-[60ch] text-[15px] text-ink-2">{message}</p>
    </div>
  );
}

/** A stage carries the fields it produced plus its own name. Only the fields belong in the reading. */
function withoutStageName(message: ReadingStage): Partial<DeskReading> {
  return Object.fromEntries(
    Object.entries(message).filter(([key]) => key !== 'stage'),
  ) as Partial<DeskReading>;
}

function counted(reading: Partial<DeskReading>): string {
  const checked = reading.verification?.grounded.length ?? 0;
  const missed = (reading.verification?.issues.length ?? 0) + (reading.letter?.gaps.length ?? 0);
  if (checked === 0) return 'nog niets gecontroleerd';
  return missed === 0 ? `${checked} gecontroleerd` : `${checked} gecontroleerd, ${missed} niet`;
}

function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
}
