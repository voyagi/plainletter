import type { Metadata } from 'next';
import Link from 'next/link';
import { LetterSheet } from '@/components/LetterSheet';
import { Numeral } from '@/components/Numeral';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Wordmark } from '@/components/Wordmark';
import exported from '@/data/sample-reading.json';
import { dutchDays } from '@/lib/language';
import { keyFor, type DeskReading } from '@/lib/reading';

// The page is a marked-up letter. It explains the product by doing the product, on one real
// sample letter, rather than becoming a hero followed by feature cards. Every numeral below is
// read out of the reading itself, so the copy cannot end up pointing at a mark that moved.

const reading = exported.reading as unknown as DeskReading;
const READ_ON = '21 August 2026';

export const metadata: Metadata = {
  title: 'Plainletter',
  description:
    'Every country sends its residents letters they cannot read. At a free help desk in a Dutch public library, someone photographs the letter and the desk reads it back in Dutch and in their own language, with every date and amount marked on the paper it came from.',
  alternates: { canonical: '/' },
};

function Note({
  tag,
  heading,
  children,
}: {
  tag: string;
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section className="py-6">
      <span className="mb-2.5 block text-xs tracking-[0.12em] text-ink-2 uppercase">{tag}</span>
      <h2 className="m-0 mb-2.5 font-brand text-[23px] leading-[1.24] font-bold tracking-[-0.02em]">
        {heading}
      </h2>
      {children}
    </section>
  );
}

function Mark({ name }: { name: string }) {
  const number = keyFor(reading.letter, name);
  return number ? <Numeral n={number} /> : null;
}

export default function Landing() {
  const deadline = reading.deadline;
  const gap = reading.letter.gaps[0];
  const dutch = reading.explanations.find((item) => item.language === 'nl');
  const visitor = reading.explanations.find((item) => item.language === 'uk');

  return (
    <main>
      <div className="grid items-start justify-center gap-x-14 px-7 pt-10 [grid-template-columns:minmax(0,545px)_minmax(0,410px)] max-[980px]:grid-cols-1 max-[980px]:gap-0 max-[980px]:pt-6">
        <div className="sticky top-6 self-start max-[980px]:static">
          <LetterSheet letter={reading.letter} className="!text-[14.5px] !leading-[1.66]" />
        </div>

        <div>
          <header className="pb-2">
            <div className="flex items-center justify-between gap-4">
              <Wordmark as="text" />
              <ThemeToggle />
            </div>
            <h1 className="mt-5 mb-3.5 font-brand text-[clamp(30px,3.1vw,42px)] leading-[1.06] font-bold tracking-[-0.03em]">
              Put the letter down. Leave knowing what to do.
            </h1>
            <p className="m-0 mb-2.5 max-w-[30em] text-[17px] text-ink-2">
              Every country sends its residents letters they cannot read, and most answer it the
              same way: a free help desk, usually in a library. This is one of those desks, in the
              Netherlands. Someone photographs the letter, and the desk reads it back in Dutch and
              in their own language, with every date and amount marked on the paper it came from.
            </p>
            <p className="m-0 max-w-[30em] text-[17px] text-ink-2">
              This page is one of those letters. Everything down this margin is what the desk said
              about it when it read it, on {READ_ON}.
            </p>
          </header>

          <Note
            tag="The amounts"
            heading="Nothing is retyped from memory"
          >
            <p className="m-0 mb-2.5 text-[16px] text-ink-2">
              Marks <Mark name="line_amount_1" /> <Mark name="line_amount_2" /> and{' '}
              <Mark name="total_amount" /> are read off the page and then checked back against it by
              plain arithmetic rather than by the model that read them. If the two disagree, the
              whole reading is refused and nothing prints.
            </p>
          </Note>

          <Note tag="The deadline" heading="One date decides everything">
            <p className="m-0 mb-2.5 text-[16px] text-ink-2">
              Mark <Mark name="deadline" /> is the only date the letter gives. The days left are
              worked out on a real calendar, Dutch public holidays included, along with the last day
              a posted objection still arrives in time.
            </p>
            {deadline ? (
              <p className="m-0 text-[16px]">
                <b>
                  {deadline.on_written}, nog {deadline.days_left} {dutchDays(deadline.days_left)}.
                  {deadline.post_by_written ? ` Post uiterlijk ${deadline.post_by_written}.` : ''}
                </b>
              </p>
            ) : null}
          </Note>

          <Note
            tag="Both languages"
            heading="What happens if you do nothing, in a language you read"
          >
            <p className="m-0 mb-3 text-[16px] text-ink-2">
              Mark <Mark name="consequence_1" /> is the sentence nobody reads twice. It arrives at
              equal width in both languages, each set in a face drawn for its own script.
            </p>
            <div className="rounded-[10px] border border-rule px-4 py-3.5">
              <p lang="nl" className="m-0 text-[16px]">
                {dutch?.if_you_do_nothing}
              </p>
              <p lang="uk" className="mt-2.5 mb-0 border-t border-rule pt-2.5 font-cyrillic text-[16px]">
                {visitor?.if_you_do_nothing}
              </p>
            </div>
          </Note>

          <Note
            tag="The broken key, beside Kenteken"
            heading="When it cannot read something, it says so"
          >
            <p className="m-0 mb-2.5 text-[16px] text-ink-2">
              The middle character of the number plate is blurred, so there is no mark and no number
              beside that line. What the desk prints instead is the question to ask out loud:
            </p>
            <p lang="nl" className="m-0 mb-2.5 border-l-2 border-mark pl-3 text-[16px]">
              {gap?.reason} <b className="text-ink">{gap?.ask_the_visitor}</b>
            </p>
            <p className="m-0 text-[16px] text-ink-2">
              This is the part that matters most. A wrong deadline at a help desk is worse than no
              deadline.
            </p>
          </Note>

          <Note tag="The route out" heading="Then the way forward, with the address on it">
            <p className="m-0 mb-2.5 text-[16px] text-ink-2">
              Mark <Mark name="objection_route" /> is the appeal paragraph the letter prints itself.
              Objections,
              payment plans and appeals go to different places with different windows, so each step
              carries the official route it came from and the date that route was checked.
            </p>
            <p className="m-0 text-[16px] text-ink-2">
              Where a sender has not been checked against an official page, the desk says so and
              sends the visitor to Het Juridisch Loket instead of guessing.
            </p>
          </Note>
        </div>
      </div>

      <section className="mx-auto mt-10 max-w-[1014px] px-7">
        <span className="mb-2.5 block text-xs tracking-[0.12em] text-ink-2 uppercase">
          What happens to the letter
        </span>
        <h2 className="m-0 mb-2.5 font-brand text-[23px] leading-[1.24] font-bold tracking-[-0.02em]">
          A promise nobody can check is worth less than a table anybody can
        </h2>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full border-collapse text-sm">
            <thead>
              <tr>
                {['What enters', 'Why', 'Who sees it', 'Gone'].map((head) => (
                  <th
                    key={head}
                    className="border-b border-rule pt-0 pr-2.5 pb-2 text-left text-[11px] font-bold tracking-[0.1em] text-ink-2 uppercase"
                  >
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {RETENTION.map((row) => (
                <tr key={row[0]}>
                  {row.map((cell, index) => (
                    <td
                      key={index}
                      className={`border-b border-rule py-2 pr-2.5 align-top ${
                        index === 3 ? 'pr-0 font-bold text-ink' : 'text-ink-2'
                      }`}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[15px] text-ink-2">
          <Link href="/privacy">How privacy works, in full</Link>
        </p>
      </section>

      <section className="mx-auto mt-16 grid max-w-[1014px] items-center gap-14 px-7 [grid-template-columns:minmax(0,380px)_minmax(0,1fr)] max-[980px]:grid-cols-1 max-[980px]:gap-8">
        <div className="relative aspect-[1/1.414] w-full max-w-[380px] overflow-hidden rounded bg-white shadow-sheet grayscale">
          <iframe
            title="The desk card as it prints, on one A4 sheet"
            src="/sample-card"
            loading="lazy"
            tabIndex={-1}
            className="absolute top-0 left-0 h-[1123px] w-[794px] origin-top-left scale-[0.4786] border-0"
          />
        </div>
        <div>
          <span className="block text-xs tracking-[0.12em] text-ink-2 uppercase">
            The thing that goes home
          </span>
          <h2 className="mt-3 mb-3.5 font-brand text-[clamp(26px,3.2vw,38px)] leading-[1.12] font-bold tracking-[-0.03em]">
            One sheet, both languages, and a black and white printer
          </h2>
          <p className="m-0 mb-3 max-w-[34em] text-[17px] text-ink-2">
            Library printers are monochrome, so nothing on the card carries meaning in colour.
            Urgency is a word and a treatment, the hatch survives greyscale, and the marks are
            numbered at the foot against the passages they came from.
          </p>
          <p className="m-0 mb-4 max-w-[34em] text-[17px] text-ink-2">
            A calendar reminder for the deadline goes home with it.
          </p>
          <a href="/sample-card" className="text-[15px]">
            Open the card on its own page
          </a>
        </div>
      </section>

      <section className="mx-auto mt-20 max-w-[1014px] px-7 pb-5">
        <h2 className="m-0 mb-3.5 max-w-[16em] font-brand text-[clamp(28px,3.4vw,40px)] leading-[1.1] font-bold tracking-[-0.03em]">
          Bring Plainletter to your library
        </h2>
        <p className="m-0 mb-5 max-w-[44em] text-[17px] text-ink-2">
          There are 861 Informatiepunt Digitale Overheid desks in Dutch public libraries. This is
          built for the volunteers at them and for the people sitting across the table. It is open
          source, it runs in the EU, and it needs no account to try.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/desk"
            className="inline-block rounded-lg border border-ink bg-ink px-5 py-3 text-base font-bold text-paper no-underline"
          >
            Open the desk console
          </Link>
          <Link
            href="/privacy"
            className="inline-block rounded-lg border border-ink px-5 py-3 text-base font-bold no-underline"
          >
            See how privacy works
          </Link>
        </div>
      </section>

      <footer className="mx-auto mt-14 max-w-[1014px] border-t border-rule px-7 pt-5 pb-12 text-sm text-ink-2">
        Plainletter is open source under Apache-2.0. Built with the Strands Agents SDK on Amazon
        Bedrock, EU region. Sample letters are invented: the names, addresses and numbers in them
        belong to nobody.
      </footer>
    </main>
  );
}

const RETENTION: [string, string, string, string][] = [
  ['The photo of the letter', 'To read it once', 'The model in Frankfurt', 'End of request'],
  [
    'The text on it',
    'To check every date and amount against the paper',
    'Nobody, held in memory',
    'End of request',
  ],
  [
    'Dates, amounts, sender',
    'Only if the visitor starts a case, so a return visit does not begin again',
    'The desk, on return',
    '30 days',
  ],
  ['Citizen service number, IBAN', 'Never needed', 'Masked before display', 'Never stored'],
];
