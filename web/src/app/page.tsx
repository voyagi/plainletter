// The languages the desk outputs in. This scaffold page is replaced by the designed landing page
// in phase 2; the list is here so it stays in one place and cannot drift from the product.
const LANGUAGES = [
  'Nederlands',
  'English',
  'Türkçe',
  'Українська',
  'Polski',
  'Русский',
  'Español',
  'Português',
  'Română',
  'Български',
  'Deutsch',
  '中文',
];

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-14">
      <p className="font-brand text-sm font-extrabold tracking-tight">Plainletter</p>
      <h1 className="mt-4 max-w-[16ch] font-brand text-4xl font-bold leading-[1.06] tracking-tight md:text-5xl">
        Put the letter down. Leave knowing what to do.
      </h1>
      <p className="mt-5 max-w-[46ch] text-lg text-ink-2">
        A visitor brings a letter they cannot read to a library help desk. Ten minutes later they
        leave with one printed page: what it is, by when, what happens if they do nothing, and what
        to do, in Dutch and in their own language.
      </p>

      <h2 className="mt-12 font-brand text-2xl font-bold tracking-tight">Languages</h2>
      <p className="mt-2 max-w-[52ch] text-ink-2">
        Output in the language the visitor reads, in its own alphabet, on screen and on paper.
      </p>
      <ul className="mt-4 flex flex-wrap gap-2">
        {LANGUAGES.map((language) => (
          <li key={language} className="rounded-md border border-rule px-3 py-1">
            {language}
          </li>
        ))}
      </ul>

      <footer className="mt-14 border-t border-rule pt-6 text-sm text-ink-2">
        Plainletter is open source, Apache-2.0. Built with the Strands Agents SDK on Amazon Bedrock,
        EU region, for the 861 Informatiepunt Digitale Overheid desks in Dutch public libraries.
      </footer>
    </main>
  );
}
