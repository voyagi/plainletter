import { env } from '@/env';

// Whether this desk reads a letter somebody brings, decided once for both places that need it: the
// desk page, which offers the camera and the file chooser only when the answer is yes, and the read
// route, which refuses an upload when it is no. A page that hides a button is a courtesy. The route
// is the door, so it asks the same question rather than trusting that the button was not there.
//
// A reading of a real letter ends in steps and a draft objection for that person. Those go to them
// only after a trained volunteer at the desk has checked the card, so a deployment opens uploads
// only where one is present. The samples need no such check: they are invented letters whose
// readings were recorded, and the agent answers them with a scripted model rather than a live one.

export const UPLOADS_CLOSED =
  'This desk reads only the sample letters. A letter of your own is read at a desk where a ' +
  'trained volunteer checks the card before it is handed over.';

export function uploadsOpen(): boolean {
  return env.PLAINLETTER_STAFFED_DESK === 'true';
}
