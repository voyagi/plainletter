// Which languages the desk answers in, what each one is called in its own words, and which face
// its script needs. The art direction is strict about the last one: a family that happens to
// include an alphabet is not a family drawn for it, and the person who most needs the text to read
// right is the one who notices.

export type Visitor = {
  code: string;
  own: string;
  dutch: string;
  script: 'latin' | 'cyrillic' | 'han';
};

export const VISITOR_LANGUAGES: Visitor[] = [
  { code: 'uk', own: 'Українська', dutch: 'Oekraïens', script: 'cyrillic' },
  { code: 'pl', own: 'Polski', dutch: 'Pools', script: 'latin' },
  { code: 'tr', own: 'Türkçe', dutch: 'Turks', script: 'latin' },
  { code: 'en', own: 'English', dutch: 'Engels', script: 'latin' },
  { code: 'ru', own: 'Русский', dutch: 'Russisch', script: 'cyrillic' },
  { code: 'bg', own: 'Български', dutch: 'Bulgaars', script: 'cyrillic' },
  { code: 'ro', own: 'Română', dutch: 'Roemeens', script: 'latin' },
  { code: 'es', own: 'Español', dutch: 'Spaans', script: 'latin' },
  { code: 'pt', own: 'Português', dutch: 'Portugees', script: 'latin' },
  { code: 'de', own: 'Deutsch', dutch: 'Duits', script: 'latin' },
  { code: 'zh', own: '中文', dutch: 'Chinees', script: 'han' },
];

export const DUTCH: Visitor = { code: 'nl', own: 'Nederlands', dutch: 'Nederlands', script: 'latin' };

// Kept in step with RTL_LANGUAGES in src/plainletter/render.py, which rules the printed card. No
// sample ships in one of these today, and the column still has to be right the day one does.
const RIGHT_TO_LEFT = new Set(['ar', 'fa', 'he', 'ur', 'ps']);

// The reading's five headings, in the languages the desk actually ships samples in. A language
// with no entry here gets the Dutch heading alone rather than a guess: a heading nobody has
// checked, sitting above the sentence that tells someone what happens if they do nothing, is worse
// than a heading in a language they were going to have to ask about anyway.
export type HeadingKey =
  | 'what_is_this'
  | 'amounts'
  | 'if_you_do_nothing'
  | 'what_to_do'
  | 'not_checked';

const DUTCH_HEADINGS: Record<HeadingKey, string> = {
  what_is_this: 'Wat is dit',
  amounts: 'Bedragen',
  if_you_do_nothing: 'Als u niets doet',
  what_to_do: 'Wat u nu doet',
  not_checked: 'Niet gecontroleerd',
};

const HEADINGS: Record<string, Record<HeadingKey, string> | undefined> = {
  nl: DUTCH_HEADINGS,
  uk: {
    what_is_this: 'Що це за лист',
    amounts: 'Суми',
    if_you_do_nothing: 'Якщо нічого не робити',
    what_to_do: 'Що робити зараз',
    not_checked: 'Не перевірено',
  },
  pl: {
    what_is_this: 'Co to za pismo',
    amounts: 'Kwoty',
    if_you_do_nothing: 'Jeśli nic nie zrobisz',
    what_to_do: 'Co teraz zrobić',
    not_checked: 'Niesprawdzone',
  },
  tr: {
    what_is_this: 'Bu nedir',
    amounts: 'Tutarlar',
    if_you_do_nothing: 'Hiçbir şey yapmazsanız',
    what_to_do: 'Şimdi ne yapmalı',
    not_checked: 'Doğrulanmadı',
  },
  en: {
    what_is_this: 'What this is',
    amounts: 'Amounts',
    if_you_do_nothing: 'If you do nothing',
    what_to_do: 'What to do now',
    not_checked: 'Not checked',
  },
};

/** The heading in the visitor's language, or nothing when nobody has checked that language. */
export function headingIn(code: string, key: HeadingKey): string | null {
  return HEADINGS[code]?.[key] ?? null;
}

export function dutchHeading(key: HeadingKey): string {
  return DUTCH_HEADINGS[key];
}

export function languageFor(code: string): Visitor {
  if (code === DUTCH.code) return DUTCH;
  return (
    VISITOR_LANGUAGES.find((item) => item.code === code) ?? {
      code,
      own: code.toUpperCase(),
      dutch: code.toUpperCase(),
      script: 'latin',
    }
  );
}

export function directionOf(code: string): 'ltr' | 'rtl' {
  const base = code.split('-')[0] ?? code;
  return RIGHT_TO_LEFT.has(base.toLowerCase()) ? 'rtl' : 'ltr';
}

/**
 * The class that hands a script the face drawn for it.
 *
 * Latin needs nothing: the reading face is already the page. Cyrillic needs a face that carries it
 * at all, because the reading face carries none.
 */
export function scriptClass(code: string): string {
  const script = languageFor(code).script;
  if (script === 'cyrillic') return 'font-cyrillic';
  if (script === 'han') return 'font-han';
  return '';
}
