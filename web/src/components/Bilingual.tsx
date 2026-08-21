import type { ReactNode } from 'react';
import { Keys } from '@/components/Numeral';
import { directionOf, scriptClass } from '@/lib/language';

// The two languages sit at equal width, equal weight and equal position in the order, with the key
// gutter between them so neither owns the numerals. On a phone they interleave one unit at a time
// with the visitor's language first, because the phone in that scenario is usually theirs, and
// neither language is ever hidden behind a tab.

export function VisitorText({
  language,
  className = '',
  children,
}: {
  language: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      lang={language}
      dir={directionOf(language)}
      className={`${scriptClass(language)} rtl:text-right ${className}`}
    >
      {children}
    </div>
  );
}

export function Bilingual({
  language,
  keys = [],
  dutch,
  visitor,
}: {
  language: string;
  keys?: number[];
  dutch: ReactNode;
  visitor: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[1fr_30px_1fr] items-start gap-x-4 max-[620px]:grid-cols-1 max-[620px]:gap-0">
      <div lang="nl" className="max-[620px]:order-2 max-[620px]:mt-2">
        {dutch}
      </div>
      <div className="max-[620px]:order-3 max-[620px]:mt-3 max-[620px]:border-t max-[620px]:border-dashed max-[620px]:border-rule max-[620px]:pt-2 max-[620px]:empty:hidden">
        <Keys numbers={keys} />
      </div>
      <VisitorText language={language} className="max-[620px]:order-1">
        {visitor}
      </VisitorText>
    </div>
  );
}
