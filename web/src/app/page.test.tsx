import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Home from './page';

describe('landing page', () => {
  it('lists the supported languages in their own alphabets', () => {
    render(<Home />);

    for (const language of ['Nederlands', 'Українська', 'Türkçe', 'Polski', '中文']) {
      expect(screen.getByText(language)).toBeDefined();
    }
  });
});
