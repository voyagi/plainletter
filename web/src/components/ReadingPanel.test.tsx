import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LetterSheet } from '@/components/LetterSheet';
import { ReadingPanel } from '@/components/ReadingPanel';
import { VisitorText } from '@/components/Bilingual';
import exported from '@/data/sample-reading.json';
import type { DeskReading } from '@/lib/reading';

const reading = exported.reading as unknown as DeskReading;

describe('the letter as the desk shows it', () => {
  it('washes every passage the verifier grounded and numbers it in the margin', () => {
    const { container } = render(<LetterSheet letter={reading.letter} />);
    const washed = container.querySelectorAll('mark');
    expect(washed.length).toBeGreaterThanOrEqual(reading.letter.keys.length);
    expect(container.textContent).toContain('Totaal te betalen: EUR 174,00');
  });

  it('breaks the key where the desk could not read something', () => {
    // The absence is the feature. A missing numeral cannot be mistaken for a fact, which is why
    // the refusal is a gap in the margin rather than a warning colour.
    render(<LetterSheet letter={reading.letter} />);
    expect(screen.getByRole('img', { name: 'Niet gecontroleerd' })).toBeDefined();
  });

  it('leaves the words before a mid-line passage unwashed', () => {
    const { container } = render(<LetterSheet letter={reading.letter} />);
    const line = [...container.querySelectorAll('p')].find((node) =>
      node.textContent?.startsWith('Bent u het niet eens'),
    );
    expect(line).toBeDefined();
    expect(line!.firstElementChild?.tagName).toBe('SPAN');
    expect(line!.querySelector('mark')).not.toBeNull();
  });
});

describe('the reading panel', () => {
  it('sets each heading in the visitor language as well as Dutch', () => {
    render(<ReadingPanel reading={reading} />);
    expect(screen.getByText('Wat is dit')).toBeDefined();
    expect(screen.getByText('Що це за лист')).toBeDefined();
  });

  it('gives the Dutch heading alone for a language nobody has checked', () => {
    // A heading nobody has read, sitting over the sentence that says what happens if you do
    // nothing, is worse than one the visitor was going to have to ask about anyway.
    render(<ReadingPanel reading={{ ...reading, visitor_language: 'de' }} />);
    expect(screen.getByText('Als u niets doet')).toBeDefined();
    expect(screen.queryByText(/Wenn Sie/)).toBeNull();
  });

  it('shows only amounts that carry a checked value', () => {
    const { container } = render(<ReadingPanel reading={reading} />);
    const rows = [...container.querySelectorAll('table tr')].map((row) => row.textContent);
    expect(rows).toHaveLength(3);
    expect(rows.at(-1)).toContain('EUR 174,00');

    const unchecked = {
      ...reading,
      verification: { grounded: [], issues: reading.verification.issues },
    };
    const bare = render(<ReadingPanel reading={unchecked} />);
    expect(bare.container.querySelector('table')).toBeNull();
  });

  it('prints the question to ask when a field could not be read', () => {
    render(<ReadingPanel reading={reading} />);
    expect(screen.getByText('kenteken staat niet vast')).toBeDefined();
    expect(
      screen.getByText('Vraag de bezoeker het kenteken van de brief voor te lezen.'),
    ).toBeDefined();
  });

  it('says so plainly when every claim stood in the letter', () => {
    const clean = { ...reading, letter: { ...reading.letter, gaps: [] } };
    render(<ReadingPanel reading={clean} />);
    expect(screen.getByText('Alles wat de balie noemt staat in de brief zelf.')).toBeDefined();
  });

  it('holds a block at its height while that stage is still running', () => {
    render(<ReadingPanel reading={{ letter: reading.letter, visitor_language: 'uk' }} />);
    expect(screen.getByText('De balie leest de brief.')).toBeDefined();
  });
});

describe('a visitor column', () => {
  it('reads to its own edge when the language runs right to left', () => {
    const { container } = render(
      <VisitorText language="he">
        <p>שלום</p>
      </VisitorText>,
    );
    const column = container.firstElementChild as HTMLElement;
    expect(column.getAttribute('dir')).toBe('rtl');
    expect(column.getAttribute('lang')).toBe('he');
  });

  it('does not flip a left to right language', () => {
    const { container } = render(
      <VisitorText language="uk">
        <p>Привіт</p>
      </VisitorText>,
    );
    const column = container.firstElementChild as HTMLElement;
    expect(column.getAttribute('dir')).toBe('ltr');
    expect(column.className).toContain('font-cyrillic');
  });
});

describe('the steps', () => {
  it('writes a route the way a person types it off paper', () => {
    render(<ReadingPanel reading={reading} />);
    const link = screen.getAllByRole('link')[0];
    expect(link).toBeDefined();
    expect(within(link!).getByText('cjib.nl/verkeersboete')).toBeDefined();
    expect(link!.getAttribute('href')).toBe('https://www.cjib.nl/verkeersboete');
  });
});
