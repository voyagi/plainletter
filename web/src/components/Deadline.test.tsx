import { render, screen } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';
import { Deadline } from '@/components/Deadline';
import { dutchDays } from '@/lib/language';
import type { DeadlineView } from '@/lib/reading';

// The screen and the printed card are read side by side over the same number, so the console has
// to count the way src/plainletter/locales/nl.py counts: singular at exactly one, plural
// everywhere else, zero included. It said "nog 1 dagen" on the day before a deadline.

beforeAll(() => {
  // jsdom ships no matchMedia, and the counting numeral asks it whether motion is wanted.
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});

function deadlineIn(days: number): DeadlineView {
  return {
    on: '2026-09-15',
    days_left: days,
    urgency: days < 0 ? 'overdue' : 'due_soon',
    post_by: null,
    on_written: '15 september 2026',
    post_by_written: null,
  };
}

function lineOf(days: number): string {
  const { container } = render(<Deadline deadline={deadlineIn(days)} />);
  return container.textContent ?? '';
}

describe('the day count on the screen', () => {
  it('says one day in the singular', () => {
    expect(lineOf(1)).toContain('nog 1 dag');
    expect(lineOf(1)).not.toContain('1 dagen');
  });

  it('says one day late in the singular', () => {
    expect(lineOf(-1)).toContain('1 dag te laat');
    expect(lineOf(-1)).not.toContain('1 dagen');
  });

  it('says the deadline itself in the plural', () => {
    expect(lineOf(0)).toContain('nog 0 dagen');
  });

  it('still says an ordinary count in the plural', () => {
    // The control on the other side: the fix must not have made every count singular.
    expect(lineOf(25)).toContain('dagen');
  });

  it('never shows a numeral the word beside it does not fit', () => {
    // The count-up animation used to write a nought into the numeral on its first frame, which
    // under a singular word reads as a count of no days in the singular for as long as it runs.
    render(<Deadline deadline={deadlineIn(1)} />);
    expect(screen.queryByText('0')).toBeNull();
  });
});

describe('the word for a number of days', () => {
  it('is singular at exactly one and plural everywhere else', () => {
    expect(dutchDays(1)).toBe('dag');
    expect(dutchDays(-1)).toBe('dag');
    expect(dutchDays(0)).toBe('dagen');
    expect(dutchDays(2)).toBe('dagen');
    expect(dutchDays(25)).toBe('dagen');
  });
});
