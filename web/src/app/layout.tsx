import type { Metadata } from 'next';
import {
  Atkinson_Hyperlegible_Next,
  Bricolage_Grotesque,
  Noto_Sans_Arabic,
} from 'next/font/google';
import '@/app/globals.css';
import '@/env';

// The brand layer only: the wordmark, the one plain sentence and landing headlines. It never
// reaches a control, a table or the printed card.
const bricolage = Bricolage_Grotesque({
  subsets: ['latin'],
  weight: ['400', '600', '700', '800'],
  variable: '--font-bricolage',
  display: 'swap',
});

// latin-ext is not optional here. Polish and Turkish are two of the twelve visitor languages, and
// their letters live in that subset: without it, the l with stroke and the dotless i fall out of
// the face mid-sentence and land on whatever the device happens to have.
const hyperlegible = Atkinson_Hyperlegible_Next({
  subsets: ['latin', 'latin-ext'],
  weight: ['400', '600', '700'],
  variable: '--font-hyperlegible',
  display: 'swap',
});

// Arabic gets a face drawn for Arabic rather than one that merely covers it. Vazirmatn, which the
// Farsi output uses, calls itself a Persian project first, and Persian prefers letter shapes an
// Arabic reader would not choose. Every script here gets its own designed face for that reason.
const arabic = Noto_Sans_Arabic({
  subsets: ['arabic'],
  weight: ['400', '600', '700'],
  variable: '--font-arabic',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Plainletter',
  description:
    'Plainletter reads an official Dutch letter at a library help desk and explains it in plain language, in Dutch and in the language the visitor reads, with every date and amount taken from the letter itself.',
  openGraph: {
    title: 'Plainletter',
    description:
      'An agent behind the help desk where newcomers bring official letters they cannot read.',
    type: 'website',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${bricolage.variable} ${hyperlegible.variable} ${arabic.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
