const LANGUAGES = [
  'Nederlands',
  'English',
  'العربية',
  'Türkçe',
  'Українська',
  'Polski',
  'فارسی',
  'Español',
  'Português',
  '中文',
  'Русский',
  'עברית',
];

export default function Home() {
  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-[96px_1fr]">
      <aside className="hidden border-e-[3px] border-rule bg-signal md:block" aria-hidden="true" />
      <main>
        <section className="border-b-[3px] border-rule px-6 py-10 md:px-14 md:py-12">
          <p className="font-board text-xs font-bold uppercase tracking-[0.2em]">Plainletter</p>
          <h1 className="mt-3 max-w-[15ch] font-board text-4xl font-extrabold leading-[1.02] md:text-6xl">
            The letter goes home explained.
          </h1>
          <p className="mt-5 max-w-[46ch] text-xl">
            A visitor brings a letter they cannot read to a library help desk. Ten minutes later
            they leave with one printed page: what it is, by when, what happens if they do nothing,
            and what to do, in Dutch and in their own language.
          </p>
        </section>

        <section className="border-b-[3px] border-rule px-6 py-10 md:px-14">
          <h2 className="font-board text-2xl font-extrabold md:text-3xl">Languages</h2>
          <p className="mt-2 max-w-[52ch]">
            Output in the language the visitor reads, right-to-left scripts included, on screen and
            on paper.
          </p>
          <ul className="mt-4 flex flex-wrap gap-3">
            {LANGUAGES.map((language) => (
              <li key={language} className="border-2 border-rule px-3 py-1">
                {language}
              </li>
            ))}
          </ul>
        </section>

        <footer className="px-6 py-8 text-quiet md:px-14">
          Plainletter is open source, Apache-2.0. Built with the Strands Agents SDK on Amazon
          Bedrock, EU region, for the 861 Informatiepunt Digitale Overheid desks in Dutch public
          libraries.
        </footer>
      </main>
    </div>
  );
}
