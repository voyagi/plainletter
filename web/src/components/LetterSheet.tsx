import type { MarkedLetter } from '@/lib/reading';
import { BrokenKey, Numeral } from '@/components/Numeral';

// The letter, as photographed or typed, with every used passage washed and numbered in the margin.
// The runs come from the agent already cut: matching a passage to characters is the verifier's
// own comparison, and doing it a second time here would be a second opinion about what the letter
// says.

export function LetterSheet({
  letter,
  className = '',
  tilt = true,
}: {
  letter: MarkedLetter;
  className?: string;
  tilt?: boolean;
}) {
  return (
    <div
      className={`wash-on rounded-[10px] bg-paper px-6 py-7 pl-[18px] text-[13.5px] leading-[1.62] shadow-sheet ${
        tilt ? 'rotate-[-0.35deg] max-[1000px]:rotate-0' : ''
      } ${className}`}
    >
      {letter.lines.map((line, index) => (
        <div
          key={index}
          className="grid min-h-[1.62em] grid-cols-[22px_1fr] items-start gap-3"
        >
          <span>
            {line.mark !== null ? <Numeral n={line.mark} /> : null}
            {line.gap ? <BrokenKey /> : null}
          </span>
          <p className="m-0 whitespace-pre-wrap break-words">
            {line.runs.map((run, position) =>
              run.mark === null ? (
                <span key={position}>{run.text}</span>
              ) : (
                <mark key={position}>{run.text}</mark>
              ),
            )}
          </p>
        </div>
      ))}
    </div>
  );
}
