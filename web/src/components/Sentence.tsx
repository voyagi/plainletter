import { VisitorText } from '@/components/Bilingual';
import { explanationFor, type DeskReading } from '@/lib/reading';

// The first thing a frightened person reads. One large plain sentence in their language with the
// Dutch directly beneath it, and only the two facts that decide everything are marked, so the
// marks keep meaning something. Not five tiles: nobody arrives wanting a dashboard of their own
// fine.

export function Sentence({ reading }: { reading: Partial<DeskReading> }) {
  const language = reading.visitor_language ?? 'en';
  const dutch = explanationFor(reading, 'nl');
  const visitor = explanationFor(reading, language) ?? dutch;

  if (!dutch) {
    return (
      <div className="min-h-[7.5rem] pt-8">
        <p className="m-0 font-brand text-[29px] leading-[1.38] font-semibold tracking-[-0.02em] text-ink-3">
          De balie leest de brief.
        </p>
      </div>
    );
  }

  return (
    <div className="wash-on max-w-[1000px] pt-8">
      {visitor ? (
        <VisitorText language={language}>
          <p className="m-0 text-[29px] leading-[1.62] font-semibold">
            <Marked
              text={visitor.what_is_this}
              values={markable(reading)}
            />
          </p>
        </VisitorText>
      ) : null}
      <p
        lang="nl"
        className="mt-3 mb-0 font-brand text-[29px] leading-[1.38] font-semibold tracking-[-0.02em]"
      >
        <Marked text={dutch.what_is_this} values={markable(reading)} />
      </p>
    </div>
  );
}

/** The checked total and the checked deadline, and nothing else. */
function markable(reading: Partial<DeskReading>): string[] {
  const wanted = new Set(['total_amount', 'deadline']);
  return (reading.verification?.grounded ?? [])
    .filter((fact) => wanted.has(fact.name))
    .map((fact) => fact.display);
}

/**
 * Wash the given values where they stand in the sentence.
 *
 * Only values the verifier grounded are ever passed in, so this cannot highlight something the
 * letter does not say. Each washed value is isolated because a right-to-left sentence would
 * otherwise let the bidirectional algorithm reorder the amount.
 */
export function Marked({ text, values }: { text: string; values: string[] }) {
  const found = values.filter((value) => value && text.includes(value));
  if (found.length === 0) return <>{text}</>;

  const pattern = new RegExp(`(${found.map(escapeRegExp).join('|')})`, 'g');
  return (
    <>
      {text.split(pattern).map((piece, index) =>
        found.includes(piece) ? (
          <mark key={index}>
            <bdi>{piece}</bdi>
          </mark>
        ) : (
          <span key={index}>{piece}</span>
        ),
      )}
    </>
  );
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
