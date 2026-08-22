// The shape the agent sends, mirrored for the console. The agent is the source of truth: every
// field here exists in src/plainletter/schemas.py under the same name, and a reading arrives as a
// sequence of partials that merge into one of these.

export type SourceSpan = { page: number; text: string };

export type Unreadable = {
  field: string;
  reason: string;
  ask_the_visitor: string;
};

export type LetterRun = { text: string; mark: number | null };

export type LetterLine = { runs: LetterRun[]; mark: number | null; gap: boolean };

export type MarkKey = { number: number; text: string; facts: string[] };

export type MarkedLetter = {
  lines: LetterLine[];
  keys: MarkKey[];
  gaps: Unreadable[];
  unplaced: string[];
};

export type Money = { currency: string; cents: number; label: string; source: SourceSpan };

export type NamedValue = { value: string; source: SourceSpan };

export type LetterFacts = {
  sender_id: string | null;
  sender_name: NamedValue | null;
  letter_type: NamedValue | null;
  reference: NamedValue | null;
  total_amount: Money | null;
  line_amounts: Money[];
  unreadable: Unreadable[];
};

export type VerificationIssue = {
  name: string;
  problem: string;
  claimed: string;
  span_text: string | null;
};

export type GroundedFact = { name: string; display: string; span: SourceSpan };

export type VerificationResult = { grounded: GroundedFact[]; issues: VerificationIssue[] };

export type Urgency = 'overdue' | 'due_soon' | 'ample' | 'unknown';

export type DeadlineView = {
  on: string;
  days_left: number;
  urgency: Urgency;
  post_by: string | null;
  // Written by the agent, not here. The console and the printed card must say the same date in the
  // same words, and a second date formatter is a second chance to disagree.
  on_written: string;
  post_by_written: string | null;
};

export type Explanation = {
  language: string;
  what_is_this: string;
  by_when: string;
  if_you_do_nothing: string;
};

export type ActionStep = {
  order: number;
  dutch: string;
  visitor: string;
  official_route: string | null;
};

export type DraftLetter = {
  kind: 'objection' | 'payment_plan' | 'reply';
  addressed_to: string;
  send_before: string | null;
  dutch: string;
  visitor: string;
};

export type Handoff = { required: boolean; referral: string; reason: string };

export type DeskReading = {
  facts: LetterFacts;
  verification: VerificationResult;
  letter: MarkedLetter;
  deadline: DeadlineView | null;
  sender_name: string;
  letter_type: string;
  visitor_language: string;
  explanations: Explanation[];
  steps: ActionStep[];
  draft: DraftLetter | null;
  handoff: Handoff;
  sources: string[];
};

// A stage carries the fields it just produced and nothing else, so a partial reading is a reading
// with holes rather than a different shape. One renderer draws both.
export type ReadingStage = Partial<DeskReading> & { stage: string };

// One earlier reading under a case the visitor asked the desk to keep: derived values only, the
// same ones the agent stored, so the desk can say "last time it was this letter, due then".
export type CaseRecord = {
  case_id: string;
  read_on: string;
  visitor_language: string;
  sender_id: string | null;
  sender_name: string;
  letter_type: string;
  reference: string | null;
  issued_on: string | null;
  deadline: string | null;
  post_by: string | null;
  urgency: Urgency | null;
  total_amount: string | null;
  steps: ActionStep[];
  handoff_required: boolean;
  referral: string;
};

export type CaseInfo = {
  id: string | null;
  remembered: boolean;
  earlier: CaseRecord[];
  note?: string;
};

export type CaseMessage = { stage: 'case'; case: CaseInfo };

export type DoneMessage = {
  stage: 'done';
  source: 'sample' | 'letter';
  pages: number;
  pages_omitted: number;
  reading: DeskReading;
  case: CaseInfo | null;
  desk_card_html: string;
  reminder_ics: string | null;
};

export type RefusedMessage = {
  stage: 'refused';
  refused: true;
  claims: string[];
  message: string;
};

export type ErrorMessage = { error: { kind: string; detail: string } };

export type AgentMessage =
  | ReadingStage
  | CaseMessage
  | DoneMessage
  | RefusedMessage
  | ErrorMessage;

export function isError(message: AgentMessage): message is ErrorMessage {
  return 'error' in message;
}

export function isRefusal(message: AgentMessage): message is RefusedMessage {
  return 'stage' in message && message.stage === 'refused';
}

export function isDone(message: AgentMessage): message is DoneMessage {
  return 'stage' in message && message.stage === 'done';
}

export function isCase(message: AgentMessage): message is CaseMessage {
  return 'stage' in message && message.stage === 'case';
}

export const STAGE_ORDER = [
  'facts',
  'letter',
  'deadline',
  'explanations',
  'steps',
  'draft',
] as const;

export function explanationFor(
  reading: Partial<DeskReading>,
  language: string,
): Explanation | undefined {
  return reading.explanations?.find((item) => item.language === language);
}

/** The numeral written beside the passage a named fact came from, when it has one. */
export function keyFor(letter: MarkedLetter | undefined, name: string): number | undefined {
  return letter?.keys.find((key) => key.facts.includes(name))?.number;
}

/**
 * The checked value for a named fact, exactly as the verifier wrote it.
 *
 * The console never formats a date or an amount itself. Every number on screen is the string the
 * verifier produced when it matched that value against the letter, so a value that failed the
 * check has nothing to display and simply does not appear.
 */
export function groundedDisplay(
  reading: Partial<DeskReading>,
  name: string,
): string | undefined {
  return reading.verification?.grounded.find((fact) => fact.name === name)?.display;
}

/**
 * The marks behind the values a sentence quotes.
 *
 * A step that says "pay EUR 174,00 quoting 8194 5523 7761" is leaning on two passages of the
 * letter, and the numerals are how the volunteer points at them. The link is derived from the
 * checked values themselves rather than declared, so a sentence can only claim a mark by actually
 * carrying the value that mark grounded.
 */
export function keysQuotedIn(reading: Partial<DeskReading>, text: string): number[] {
  const seen = new Set<number>();
  for (const fact of reading.verification?.grounded ?? []) {
    if (!text.includes(fact.display)) continue;
    const key = keyFor(reading.letter, fact.name);
    if (key !== undefined) seen.add(key);
  }
  return [...seen].sort((a, b) => a - b);
}

/** The amounts the letter itemises, in the order it printed them, checked value and all. */
export function groundedAmounts(
  reading: Partial<DeskReading>,
): { label: string; display: string; mark: number | undefined }[] {
  const lines = (reading.facts?.line_amounts ?? []).map((amount, index) => ({
    amount,
    name: `line_amount_${index + 1}`,
  }));
  const total = reading.facts?.total_amount
    ? [{ amount: reading.facts.total_amount, name: 'total_amount' }]
    : [];
  return [...lines, ...total].flatMap(({ amount, name }) => {
    const display = groundedDisplay(reading, name);
    return display
      ? [{ label: amount.label, display, mark: keyFor(reading.letter, name) }]
      : [];
  });
}
