import type { Metadata } from 'next';
import { DeskConsole } from '@/components/console/DeskConsole';
import samples from '@/data/samples.json';

export const metadata: Metadata = {
  title: 'Desk console',
  description:
    'The console a volunteer uses at the counter: photograph a letter, watch the checked reading arrive, print the card and download the reminder.',
  // A working surface, not a page to be found in a search result. The letter on screen belongs to
  // whoever is sitting at the desk.
  robots: { index: false, follow: false },
};

export default function DeskPage() {
  return <DeskConsole samples={samples} />;
}
