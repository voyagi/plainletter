'use client';

import { useSyncExternalStore } from 'react';

// Three states, and the third one is the point: a person who has chosen nothing follows their
// device. Choosing here writes the choice down so the counter tablet keeps it between visitors.
//
// The theme lives on the document element, put there before the first paint by a script in the
// head, so this component reads it rather than owning it. That is what keeps the button and the
// page from ever disagreeing about which theme is on.

const KEY = 'plainletter-theme';
const CHANGED = 'plainletter-theme-changed';

type Theme = 'light' | 'dark';

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, current, () => 'light' as Theme);
  const dark = theme === 'dark';

  function choose(next: Theme) {
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem(KEY, next);
    window.dispatchEvent(new Event(CHANGED));
  }

  return (
    <button
      type="button"
      onClick={() => choose(dark ? 'light' : 'dark')}
      className="rounded-md border border-rule px-3 py-1.5 text-sm"
      aria-pressed={dark}
    >
      {dark ? 'Licht' : 'Donker'}
    </button>
  );
}

function current(): Theme {
  const chosen = document.documentElement.dataset.theme;
  if (chosen === 'light' || chosen === 'dark') return chosen;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  media.addEventListener('change', onChange);
  window.addEventListener(CHANGED, onChange);
  window.addEventListener('storage', onChange);
  return () => {
    media.removeEventListener('change', onChange);
    window.removeEventListener(CHANGED, onChange);
    window.removeEventListener('storage', onChange);
  };
}
