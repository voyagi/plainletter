import { Bilingual, VisitorText } from '@/components/Bilingual';
import { BrokenKey, Keys, Numeral } from '@/components/Numeral';
import { dutchHeading, headingIn, type HeadingKey } from '@/lib/language';
import {
  explanationFor,
  groundedAmounts,
  groundedDisplay,
  keyFor,
  keysQuotedIn,
  type DeskReading,
} from '@/lib/reading';

// The reading, in a fixed order that never changes between letters: what this is, the amounts,
// what happens if nothing is done, the numbered actions with their official routes, and last, what
// could not be verified. A volunteer who has used it once knows where to look on every letter
// after that, which matters more at a counter than arranging each letter to its own strengths.

function Block({
  heading,
  language,
  children,
}: {
  heading: HeadingKey;
  language: string;
  children: React.ReactNode;
}) {
  const own = headingIn(language, heading);
  return (
    <section className="border-b border-rule py-5 last:border-b-0 last:pb-1">
      <h2 className="mb-3 text-xs font-bold tracking-[0.1em] text-ink-3 uppercase">
        <span lang="nl">{dutchHeading(heading)}</span>
        {own && language !== 'nl' ? (
          <>
            <span aria-hidden> &#183; </span>
            <VisitorText language={language} className="inline">
              {own}
            </VisitorText>
          </>
        ) : null}
      </h2>
      {children}
    </section>
  );
}

function Pending({ label }: { label: string }) {
  // The row is held at its final height before the words arrive, so nothing on the page reflows
  // under the eye of someone already struggling to read it.
  return (
    <p className="min-h-[3.1em] text-[15.5px] text-ink-3" aria-live="polite">
      {label}
    </p>
  );
}

export function ReadingPanel({ reading }: { reading: Partial<DeskReading> }) {
  const language = reading.visitor_language ?? 'en';
  const dutch = explanationFor(reading, 'nl');
  const visitor = explanationFor(reading, language) ?? dutch;
  const amounts = groundedAmounts(reading);
  const reference = groundedDisplay(reading, 'reference');
  const unreadable = reading.letter?.gaps ?? [];

  return (
    <div className="rounded-[10px] bg-paper px-6 pt-0.5 pb-6 shadow-sheet">
      <Block heading="what_is_this" language={language}>
        {dutch && visitor ? (
          <Bilingual
            language={language}
            keys={numbers(
              keyFor(reading.letter, 'letter_type'),
              keyFor(reading.letter, 'sender_name'),
            )}
            dutch={<p className="m-0 text-[15.5px]">{dutch.what_is_this}</p>}
            visitor={<p className="m-0 text-[15.5px]">{visitor.what_is_this}</p>}
          />
        ) : (
          <Pending label="De balie leest de brief." />
        )}
      </Block>

      <Block heading="amounts" language={language}>
        {amounts.length > 0 ? (
          <table className="w-full border-collapse text-[15px]">
            <tbody>
              {amounts.map((amount, index) => (
                <tr key={`${amount.label}-${index}`} className="last:font-bold">
                  <td className="border-b border-rule py-1.5 last:border-b-0">{amount.label}</td>
                  <td className="w-[30px] border-b border-rule py-1.5 text-center">
                    {amount.mark ? <Numeral n={amount.mark} /> : null}
                  </td>
                  <td className="border-b border-rule py-1.5 text-right">
                    <bdi>{amount.display}</bdi>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="m-0 text-[15px] text-ink-2">Deze brief noemt geen bedrag.</p>
        )}
        {reference ? (
          <p className="mt-3 mb-0 text-[14px] text-ink-2">
            Kenmerk <b className="font-bold text-ink">{reference}</b>{' '}
            {keyFor(reading.letter, 'reference') ? (
              <Numeral n={keyFor(reading.letter, 'reference') as number} />
            ) : null}
            <br />
            Dit nummer noemt u bij elke betaling.
          </p>
        ) : null}
      </Block>

      <Block heading="if_you_do_nothing" language={language}>
        {dutch && visitor ? (
          <Bilingual
            language={language}
            keys={numbers(keyFor(reading.letter, 'consequence_1'))}
            dutch={<p className="m-0 text-[15.5px]">{dutch.if_you_do_nothing}</p>}
            visitor={<p className="m-0 text-[15.5px]">{visitor.if_you_do_nothing}</p>}
          />
        ) : (
          <Pending label="Nog niet gelezen." />
        )}
      </Block>

      <Block heading="what_to_do" language={language}>
        {reading.steps && reading.steps.length > 0 ? (
          <ol className="m-0 list-none p-0">
            {reading.steps.map((step) => (
              <li
                key={step.order}
                className="grid grid-cols-[1fr_30px_1fr] gap-x-4 border-t border-rule py-3 first:border-t-0 first:pt-0.5 max-[620px]:grid-cols-1"
              >
                <Action order={step.order} text={step.dutch} route={step.official_route} />
                <div className="max-[620px]:order-3 max-[620px]:mt-3 max-[620px]:empty:hidden">
                  <Keys numbers={keysQuotedIn(reading, step.dutch)} />
                </div>
                <VisitorText language={language} className="max-[620px]:order-1">
                  <Action order={step.order} text={step.visitor} route={step.official_route} />
                </VisitorText>
              </li>
            ))}
          </ol>
        ) : (
          <Pending label="De balie stelt de stappen op." />
        )}
      </Block>

      <Block heading="not_checked" language={language}>
        {/* One column, in Dutch, because this is the volunteer's instruction rather than the
            visitor's reading: it is a question to ask out loud, and the answer comes back in
            whatever language the two of them are already speaking. */}
        {unreadable.length > 0 ? (
          unreadable.map((gap) => (
            <div key={gap.field} lang="nl" className="grid grid-cols-[30px_1fr] gap-x-4">
              <BrokenKey label={`${gap.field}: niet gecontroleerd`} />
              <div>
                <p className="m-0 mb-1 text-[15px] font-bold text-mark">
                  {gap.field} staat niet vast
                </p>
                <p className="m-0 text-[15.5px]">{gap.reason}</p>
                <p className="mt-1 mb-0 text-[15.5px] font-bold">{gap.ask_the_visitor}</p>
              </div>
            </div>
          ))
        ) : (
          <p className="m-0 text-[15px] text-ink-2">
            Alles wat de balie noemt staat in de brief zelf.
          </p>
        )}
        {reading.handoff?.required ? (
          <p className="mt-4 mb-0 border-l-4 border-ink pl-3 text-[15px]">
            <b>Als het ingewikkeld wordt.</b> {reading.handoff.referral}
          </p>
        ) : null}
      </Block>
    </div>
  );
}

function Action({
  order,
  text,
  route,
}: {
  order: number;
  text: string;
  route: string | null;
}) {
  return (
    <div className="grid grid-cols-[22px_1fr] items-start gap-2.5 rtl:grid-cols-[1fr_22px]">
      <span className="h-[22px] w-[22px] rounded-[4px] bg-ink text-center text-xs leading-[22px] font-bold text-paper rtl:order-2">
        {order}
      </span>
      <div className="rtl:order-1">
        {text}
        {route ? (
          <a
            className="mt-1.5 block text-[13.5px] text-ink-2 underline underline-offset-2"
            href={route}
            rel="noreferrer"
          >
            <bdi>{shortRoute(route)}</bdi>
          </a>
        ) : null}
      </div>
    </div>
  );
}

/** A route a person types off paper, so the scheme and the www prefix are noise. */
function shortRoute(url: string): string {
  return url.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/$/, '');
}

/** The marks a block leans on, in the order they stand on the letter. */
function numbers(...values: (number | undefined)[]): number[] {
  return values.filter((value): value is number => value !== undefined).sort((a, b) => a - b);
}
