import type { Metadata } from 'next';
import Link from 'next/link';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Wordmark } from '@/components/Wordmark';
import { env } from '@/env';

export const metadata: Metadata = {
  title: 'Privacy',
  description:
    'What Plainletter processes, on what legal basis, who else sees it, how long anything is kept, and how to have a case erased.',
  alternates: { canonical: '/privacy' },
};

// Who answers for the data is a fact about the deployment, not about the code, so it comes from the
// deployment's own environment. A library running its own copy is its own controller, and a name
// hard-coded here would be a false one in front of that library's visitors, at the exact line where
// Article 13 wants a real one. Unset, the page says what is true of every deployment.
const CONTROLLER = env.PLAINLETTER_CONTROLLER_NAME;
const CONTROLLER_CONTACT = env.PLAINLETTER_CONTROLLER_CONTACT;

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

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-l-2 border-rule py-2 pl-3 sm:grid-cols-[13rem_1fr] sm:gap-4">
      <b className="text-ink">{term}</b>
      <span className="text-ink-2">{children}</span>
    </div>
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
        number. Plainletter is built so that almost none of it has anywhere to go. This page says
        what happens to it, in the order the law asks for.
      </p>

      <Section heading="Who is responsible">
        {CONTROLLER ? (
          <p className="m-0 mb-3 text-[16px] text-ink-2">
            The data controller for this desk is {CONTROLLER}
            {CONTROLLER_CONTACT ? (
              <>
                , reachable at{' '}
                <a className="underline underline-offset-2" href={`mailto:${CONTROLLER_CONTACT}`}>
                  {CONTROLLER_CONTACT}
                </a>
              </>
            ) : null}
            . The controller decides what this desk does with a letter and answers for it.
          </p>
        ) : (
          <p className="m-0 mb-3 text-[16px] text-ink-2">
            The data controller is the organisation running this desk. The controller decides what
            this desk does with a letter and answers for it. Ask the desk for the
            controller&rsquo;s name and contact address; it is also printed on the privacy notice at
            the counter.
          </p>
        )}
        <p className="m-0 mb-3 text-[16px] text-ink-2">
          Every desk answers for its own copy. A library or advice service that runs Plainletter
          itself is the controller of that installation, and its own name belongs here rather than
          anybody else&rsquo;s.
        </p>
        <p className="m-0 text-[16px] text-ink-2">
          This desk has no data protection officer, because none is required of it. A public body
          running its own copy does need one and names them here. Questions go to the controller.
        </p>
      </Section>

      <Section heading="What is processed, why, and on what basis">
        <div className="text-[16px]">
          <Row term="The letter itself">
            The photograph or file, and everything printed on it, for as long as one reading takes.
            The basis is your own request: you asked this desk to read this letter.
          </Row>
          <Row term="A case you agreed to keep">
            Only if you say yes out loud. The basis is your consent, and you can take it back at any
            moment by asking for the case to be erased.
          </Row>
          <Row term="Counts about the service">
            How many facts were checked, whether a person was needed, which sender the letter came
            from. No sentence of any letter. The basis is the legitimate interest in knowing whether
            the service works.
          </Row>
          <Row term="Keeping the desk standing">
            A network address and a random marker in a cookie, so one caller cannot use up the
            service. The basis is the legitimate interest in security, and that cookie is strictly
            necessary for it, so it is set without asking.
          </Row>
        </div>
        <p className="m-0 mt-4 text-[16px] text-ink-2">
          Handing over the letter is voluntary and nothing obliges you to. Without it there is
          nothing to read, which is the only consequence.
        </p>
      </Section>

      <Section heading="Where it goes">
        <p className="m-0 mb-3 text-[16px] text-ink-2">
          The letter goes to an Amazon Bedrock model hosted in the European Union, reached from the
          Frankfurt region, and to Amazon Bedrock AgentCore, which runs this service and holds a
          consented case. Both are processors: they act on the controller&rsquo;s instructions and
          on nobody else&rsquo;s. Nothing is sent outside the EU in normal operation, and nothing is
          sold, shared or published.
        </p>
        <p className="m-0 text-[16px] text-ink-2">
          Amazon states that Bedrock does not store model inputs or outputs, and that model
          providers have no access to them at all. Amazon does screen uploaded images for child
          sexual abuse material and may keep a flagged image to decide what it is. The full
          position, with the wording and the date it was read, is in{' '}
          <code className="text-ink">docs/privacy-accountability.md</code> in the source code.
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

      <Section heading="How long anything is kept">
        <p className="m-0 mb-3 text-[16px] text-ink-2">
          The reading stays in the tab in front of the volunteer for fifteen minutes and then clears
          itself. The clock is visible in the console while a letter is open, and{' '}
          <b className="text-ink">Brief wissen</b> ends it sooner.
        </p>
        <p className="m-0 text-[16px] text-ink-2">
          A case you agreed to keep lives for thirty days and then deletes itself. What is in it is
          the derived facts and nothing else: the sender, the letter type, the amounts, the
          deadline, the steps. Not the image, not the text, and never the masked identifiers. It is
          filed under a case number printed on your desk card, and it lives in the same EU region as
          the reading.
        </p>
      </Section>

      <Section heading="Your rights">
        <div className="text-[16px]">
          <Row term="See what is kept">
            Bring the case number on your card. The desk shows every reading filed under it, which
            is the whole record.
          </Row>
          <Row term="Have it erased">
            Ask, with the case number, and the desk deletes it there and then rather than in thirty
            days. No letter is read and nothing else is needed.
          </Row>
          <Row term="Correct it">
            A record comes from one reading. A wrong reading is read again and the old case erased.
          </Row>
          <Row term="Take it with you">
            The reading leaves with you as a printed card and a calendar reminder, and a case can be
            handed over as a file.
          </Row>
          <Row term="Restrict or object">
            Nothing is kept unless you said yes, and erasing the case takes that yes back.
          </Row>
          <Row term="Complain">
            To the controller first, and to the Autoriteit Persoonsgegevens at{' '}
            <a href="https://autoriteitpersoonsgegevens.nl">autoriteitpersoonsgegevens.nl</a> at any
            time, whatever the desk says.
          </Row>
        </div>
      </Section>

      <Section heading="No decision is made about you">
        <p className="m-0 text-[16px] text-ink-2">
          Plainletter explains a letter and lays out the options. It decides nothing about you,
          profiles nobody, and never scores or ranks a person. Where the reading did not fully check
          out, or the sender&rsquo;s procedure has not been confirmed against an official page, it
          says so and points to a person.
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
