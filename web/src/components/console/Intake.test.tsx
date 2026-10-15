import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Intake } from '@/components/console/Intake';
import samples from '@/data/samples.json';

function intake(uploads: boolean) {
  return render(
    <Intake
      samples={samples}
      uploads={uploads}
      language="uk"
      onLanguage={vi.fn()}
      memory={{ consent: false, caseId: '' }}
      onMemory={vi.fn()}
      onFile={vi.fn()}
      onSample={vi.fn()}
      busy={false}
    />,
  );
}

describe('the empty desk', () => {
  it('offers only the samples where nobody checks the card', () => {
    const { container } = intake(false);

    expect(screen.queryByRole('button', { name: 'Maak een foto' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Kies een bestand' })).toBeNull();
    expect(container.querySelector('input[type="file"]')).toBeNull();
    // The language choice only ever reached an uploaded letter, so it goes with the buttons.
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(screen.getByText(/leest alleen de voorbeeldbrieven/)).toBeDefined();
    for (const sample of samples) {
      expect(screen.getByText(sample.sender)).toBeDefined();
    }
  });

  it('offers the camera and the file chooser at a staffed desk', () => {
    const { container } = intake(true);

    expect(screen.getByRole('button', { name: 'Maak een foto' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Kies een bestand' })).toBeDefined();
    expect(container.querySelectorAll('input[type="file"]')).toHaveLength(2);
    expect(screen.getByRole('combobox')).toBeDefined();
    expect(screen.queryByText(/leest alleen de voorbeeldbrieven/)).toBeNull();
    expect(screen.getAllByRole('listitem')).toHaveLength(samples.length);
  });
});
