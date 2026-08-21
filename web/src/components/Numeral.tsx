// The numeral is the whole mechanism. It appears in four places for one fact, always the same
// number, so a volunteer can say "number four" and a visitor reading another alphabet looks at the
// same words. Where the desk could not ground something there is no numeral at all: the margin
// rule breaks instead, because a colour can be misread and a missing number cannot be mistaken for
// a fact.

export function Numeral({ n }: { n: number }) {
  return (
    <span className="inline-block h-5 w-5 rounded-[4px] border border-mark text-center text-[11px] font-bold leading-[1.6] text-mark">
      {n}
    </span>
  );
}

export function BrokenKey({ label }: { label?: string }) {
  return (
    <span
      className="mt-2.5 block w-5 border-t border-dashed border-ink-3"
      role="img"
      aria-label={label ?? 'Niet gecontroleerd'}
    />
  );
}

export function Keys({ numbers }: { numbers: number[] }) {
  return (
    <span className="flex flex-col items-center gap-1.5 pt-px max-[620px]:flex-row max-[620px]:justify-start">
      {numbers.map((n) => (
        <Numeral key={n} n={n} />
      ))}
    </span>
  );
}
