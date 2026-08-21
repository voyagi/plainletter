import type { Metadata } from 'next';
import Link from 'next/link';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Wordmark } from '@/components/Wordmark';

export const metadata: Metadata = {
  title: 'Privacy',
  description:
    'What Plainletter processes, what it never stores, where it runs, and how memory consent works.',
  alternates: { canonical: '/privacy' },
};

function Section({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-rule py-7">
      <h2 className="m-0 mb-3 font-brand text-[23px] leading-[1.24] font-bold tracking-[-0.02em]">
        {heading}
      </h2>
      {children}
    </section>
  );
}

export default function Privacy() {
  return (
    <main className="mx-auto max-w-[46rem] px-7 pt-8 pb-16">
      <div className="flex items-center justify-between gap-4">
        <Wordmark />
        <ThemeToggle />
      </div>

      <h1 className="mt-8 mb-4 font-brand text-[clamp(30px,3.1vw,42px)] leading-[1.08] font-bold tracking-[-0.03em]">
        A letter is the most personal post a person gets.
      </h1>
      <p className="m-0 mb-8 text-[17px] text-ink-2">
        An official letter carries a name, an address, an amount owed and often a citizen service
        number. Plainletter is built so that almost none of that has anywhere to go.
      </p>

      <Section heading="What is processed, and where">
        <p className="m-0 mb-3 text-[16px] text-ink-2">
          The photograph or file goes to an Amazon Bedrock model hosted in the European Union,
          reached from the Frankfurt region, for exactly as long as one reading takes. Nothing is
          sent outside the EU.
        </p>
        <p className="m-0 text-[16px] text-ink-2">
          The letter is read once. Its text is held in memory while every date and amount is checked
          against it, and it is gone when the answer comes back.
        </p>
      </Section>

      <Section heading="What is never stored">
        <ul className="m-0 list-none space-y-2 p-0 text-[16px] text-ink-2">
          <li className="border-l-2 border-rule pl-3">
            The image of the letter. It is not written to disk, not kept in a bucket, not logged.
          </li>
          <li className="border-l-2 border-rule pl-3">
            The text of the letter. The reading is derived from it and the text itself is dropped.
          </li>
          <li className="border-l-2 border-rule pl-3">
            The citizen service number and any bank account number. Both are masked before anything
            is shown on screen, printed on the card or written to a reminder, so they cannot reach a
            log by accident.
          </li>
        </ul>
      </Section>

      <Section heading="What the browser holds, and for how long">
        <p className="m-0 mb-3 text-[16px] text-ink-2">
          The reading stays in the tab in front of the volunteer for fifteen minutes and then clears
          itself. The clock is visible in the console while a letter is open, and{' '}
          <b className="text-ink">Brief wissen</b> ends it sooner.
        </p>
        <p className="m-0 text-[16px] text-ink-2">
          The browser never holds a cloud credential. It posts the letter to this application, and
          the application talks to the agent from the server side.
        </p>
      </Section>

      <Section heading="Memory, only with consent">
        <p className="m-0 mb-3 text-[16px] text-ink-2">
          A visitor who will come back can ask the desk to remember their case so the next visit
          does not start again. That is a question the volunteer asks out loud, and nothing is kept
          unless the answer is yes.
        </p>
        <p className="m-0 text-[16px] text-ink-2">
          What is kept then is the derived facts and nothing else: the sender, the letter type, the
          amounts, the deadline, the steps. Not the image, not the text, and never the masked
          identifiers. It expires after thirty days.
        </p>
      </Section>

      <Section heading="The demo letters are invented">
        <p className="m-0 text-[16px] text-ink-2">
          Every sample letter in this project is written from scratch. The names, addresses, number
          plates, reference numbers and citizen service numbers in them belong to nobody, and no
          real letter has ever been committed to this repository.
        </p>
      </Section>

      <Section heading="This is not legal advice">
        <p className="m-0 text-[16px] text-ink-2">
          Plainletter explains letters. It says plainly when a letter needs a professional, and
          points to Het Juridisch Loket, the sociaal raadslieden or municipal debt support rather
          than trying to handle it.
        </p>
      </Section>

      <p className="mt-8 text-[15px]">
        <Link href="/">Back to the letter</Link>
      </p>
    </main>
  );
}
