import { describe, expect, it } from 'vitest';
import exported from '@/data/sample-reading.json';
import {
  groundedAmounts,
  groundedDisplay,
  keyFor,
  keysQuotedIn,
  type DeskReading,
} from '@/lib/reading';

// The agent's own output, exported from its own corpus, rather than a fixture written to pass.
const reading = exported.reading as unknown as DeskReading;

describe('reading a checked letter', () => {
  it('numbers every passage the verifier grounded', () => {
    expect(reading.letter.keys.map((key) => key.number)).toEqual(
      reading.letter.keys.map((_, index) => index + 1),
    );
    expect(reading.letter.unplaced).toEqual([]);
  });

  it('shows a value only in the words the verifier checked it in', () => {
    expect(groundedDisplay(reading, 'total_amount')).toBe('EUR 174,00');
    expect(groundedDisplay(reading, 'deadline')).toBe('15 september 2026');
    expect(groundedDisplay(reading, 'no_such_fact')).toBeUndefined();
  });

  it('lists the itemised amounts before the total, each against its own mark', () => {
    const amounts = groundedAmounts(reading);
    expect(amounts.map((amount) => amount.display)).toEqual([
      'EUR 165,00',
      'EUR 9,00',
      'EUR 174,00',
    ]);
    expect(amounts.at(-1)?.label).toBe('Totaal te betalen');
    expect(amounts.every((amount) => typeof amount.mark === 'number')).toBe(true);
  });

  it('drops an amount the check never passed rather than displaying it unmarked', () => {
    const ungrounded = {
      ...reading,
      verification: { grounded: [], issues: reading.verification.issues },
    };
    expect(groundedAmounts(ungrounded)).toEqual([]);
  });

  it('links a sentence to the marks behind the values it quotes', () => {
    const step = reading.steps[0];
    expect(step).toBeDefined();
    const keys = keysQuotedIn(reading, step!.dutch);
    expect(keys).toContain(keyFor(reading.letter, 'total_amount'));
    expect(keys).toContain(keyFor(reading.letter, 'reference'));
    expect(keys).toEqual([...keys].sort((a, b) => a - b));
  });

  it('claims no mark for a sentence carrying none of the checked values', () => {
    expect(keysQuotedIn(reading, 'Een zin zonder cijfers.')).toEqual([]);
  });
});
