import type { Metadata } from 'next';
import { DeskConsole } from '@/components/console/DeskConsole';
import samples from '@/data/samples.json';
import { uploadsOpen } from '@/server/uploads';

export const metadata: Metadata = {
  title: 'Desk console',
  description:
    'The console a volunteer uses at the counter: photograph a letter, watch the checked reading arrive, print the card and download the reminder.',
  // A working surface, not a page to be found in a search result. The letter on screen belongs to
  // whoever is sitting at the desk.
  robots: { index: false, follow: false },
};

export default function DeskPage() {
  // Decided here on the server and handed down as a plain yes or no: the console is a client
  // component and may not import the module that reads the deployment's settings.
  return <DeskConsole samples={samples} uploads={uploadsOpen()} />;
}
