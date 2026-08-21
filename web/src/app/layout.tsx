import type { Metadata } from 'next';
import { Atkinson_Hyperlegible_Next, Overpass } from 'next/font/google';
import '@/app/globals.css';
import '@/env';

const overpass = Overpass({
  subsets: ['latin'],
  weight: ['600', '700', '800'],
  variable: '--font-overpass',
  display: 'swap',
});

const hyperlegible = Atkinson_Hyperlegible_Next({
  subsets: ['latin'],
  weight: ['400', '600', '700'],
  variable: '--font-hyperlegible',
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
    <html lang="en" className={`${overpass.variable} ${hyperlegible.variable}`}>
      <body>{children}</body>
    </html>
  );
}
