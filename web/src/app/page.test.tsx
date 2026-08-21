import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Home from './page';

describe('landing page', () => {
  it('lists every supported language, right-to-left scripts included', () => {
    render(<Home />);

    for (const language of ['Nederlands', 'العربية', 'Українська', 'فارسی', '中文', 'עברית']) {
      expect(screen.getByText(language)).toBeDefined();
    }
  });
});
