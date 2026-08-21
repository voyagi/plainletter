import type { Metadata, Viewport } from 'next';
import { Atkinson_Hyperlegible_Next, Bricolage_Grotesque, Noto_Sans } from 'next/font/google';
import '@/app/globals.css';
import '@/env';
import { env } from '@/env';

// The brand layer only: the wordmark, the one plain sentence and landing headlines. It never
// reaches a control, a table or the printed card.
const bricolage = Bricolage_Grotesque({
  subsets: ['latin'],
  weight: ['400', '600', '700', '800'],
  variable: '--font-bricolage',
  display: 'swap',
});

// latin-ext is not optional here. Polish and Turkish are two of the visitor languages and their
// letters live in that subset: without it, the l with stroke and the dotless i fall out of the face
// mid-sentence and land on whatever the device happens to have.
const hyperlegible = Atkinson_Hyperlegible_Next({
  subsets: ['latin', 'latin-ext'],
  weight: ['400', '600', '700'],
  variable: '--font-hyperlegible',
  display: 'swap',
});

// The reading face carries no Cyrillic at all, so Ukrainian, Russian and Bulgarian get a face that
// does. Only the Cyrillic subset is loaded: Latin inside a Ukrainian sentence, an amount or a
// street name, falls through to the reading face, which is what the rest of the page is set in.
const cyrillic = Noto_Sans({
  subsets: ['cyrillic', 'cyrillic-ext'],
  weight: ['400', '600', '700'],
  variable: '--font-noto',
  display: 'swap',
});

export const metadata: Metadata = {
  metadataBase: new URL(env.NEXT_PUBLIC_SITE_URL),
  title: {
    default: 'Plainletter',
    template: '%s - Plainletter',
  },
  description:
    'Plainletter reads an official Dutch letter at a library help desk and explains it in plain language, in Dutch and in the language the visitor reads, with every date and amount taken from the letter itself.',
  applicationName: 'Plainletter',
  openGraph: {
    title: 'Plainletter',
    description:
      'An agent behind the help desk where newcomers bring official letters they cannot read.',
    type: 'website',
    locale: 'en',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Plainletter',
    description:
      'An agent behind the help desk where newcomers bring official letters they cannot read.',
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#efeae6' },
    { media: '(prefers-color-scheme: dark)', color: '#191614' },
  ],
};

// Runs before the first paint so a chosen theme does not flash the other one. Anything longer than
// this belongs in a component, not in the document head.
const THEME = `try{var t=localStorage.getItem("plainletter-theme");if(t)document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${bricolage.variable} ${hyperlegible.variable} ${cyrillic.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
