# Art direction

Status: draft. Locked after the console, landing page and desk card are rendered as mockups at
desktop and mobile sizes and reviewed.

## Anchor: the counter and the wayfinding board

Dutch public wayfinding and postal counters, 1968 to 1989: railway station signage, post office
forms, the graphic systems built so a stranger in a station finds the right platform without
reading a paragraph. One signal colour, big sans type with a tall x-height, flat pictograms,
numbered routes, date stamps. A letter is a journey through a system the visitor does not know,
and the desk is the station counter.

## Type

- Display and board: Overpass (road-sign lineage; tabular figures for amounts and dates).
- Text and UI: Atkinson Hyperlegible Next (drawn for legibility for low-vision and low-literacy
  readers, which is this audience).
- Script companions, loaded per language: Vazirmatn for Arabic and Farsi, Noto Sans Hebrew for
  Hebrew, Noto Sans for Cyrillic (Ukrainian, Russian), Noto Sans SC for Chinese. Headings in
  non-Latin scripts use the companion face, never a Latin display face.
- Body at least 16px, 45 to 75 characters per line, line height 1.5 for reading columns.

## Colour

- Signal yellow #F5C400: the dominant surface. It appears only as the board, the card header and
  the landing spine.
- Ink #14213D: all text, borders, pictograms.
- White #FFFFFF: every reading surface, where the two languages sit.
- Overdue red #C8102E, due-soon amber #B45309, clear green #0B7A4B, action blue #1F4FBF for links
  and the one primary button. No gradients.
- Dark theme: ink surfaces #0F172A, text #F8FAFC, the same yellow as the only warm colour, the
  urgency accents lifted one step for contrast.

## Structure: the console

Reads like a counter, left to right, top to bottom.

1. The board (top): one yellow strip with five cells: LETTER (sender, type), AMOUNT, DEADLINE
   (date and "in 12 days"), URGENCY (the coloured cell), STATUS (reading, verified, ready to
   print). Cells fill in one by one as facts arrive; an empty cell shows a short dash, never a
   spinner.
2. The letter (left): the photographed or uploaded page, large, with highlights drawn onto the
   passages that carry each fact (ink outline, yellow wash), numbered to match the route card.
   Unclear passages get a dotted outline and the word "unclear" instead of a guess.
3. The route card (right): two equal columns, Dutch and the visitor's language (mirrored for
   right-to-left scripts so the visitor's column sits where it reads first). The same four headings
   in both: what this is, by when, what happens if you do nothing, what to do now (numbered steps
   with the official route and who can help). Each fact carries the number of its highlight.
4. The draft (bottom drawer): the reply or objection in Dutch with the translation beside it,
   editable, addressee and official channel printed above it.
5. The footer bar: Print desk card, Save reminder, Start a case (a consent switch with one plain
   sentence about what is kept), New letter.

## Structure: the landing page

- Opens with the desk card itself: a photograph of the printed card on a counter, the three
  questions readable in the photo, one sentence under it.
- Then the sequence: a letter, the board filling, the route card, the printed card, as four real
  frames of one session, captioned in plain English.
- Then who it is for: the help desks, a volunteer quote, the languages listed in their own scripts.
- Then privacy in a yellow-bordered box: what is processed where, what is never kept.
- Then try it: the console and the sample letters.

## Motion

Things arrive like board updates: new cells and findings slide in from the edge with a short
ease-out, highlights draw as a wipe over the letter, the deadline count settles without bounce.
Nothing fades up from below, nothing scales. Reduced motion: instant.

## Print: the desk card

A4, prints well in black and white. The yellow header band becomes a solid grey band; sender and
letter type in Overpass; the two language columns; the numbered route; a large date stamp for
the deadline in the corner; the referral point and the "not legal advice" line in the footer; a
QR code for the calendar reminder.

## Real media

Photographed sample letters (real paper, real light, real creases), the printed desk card
photographed on a counter, hands holding the card, console screenshots as real frames. No
illustration, no abstract shapes, no stock people.

## Guard rails

Yellow never becomes a page background; reading surfaces stay white and ink. No card grids, no
hero-then-sections flow, no emoji as icons, no gradients, no glass.
