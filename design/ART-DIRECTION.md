# Art direction

Locked 2026-08-21. Every page, component and piece of copy derives from this document. Mockups of
the three key surfaces live in `design/mockups/` and their renders in `design/screenshots/`.

## Anchor: the counter and the wayfinding board

Dutch public wayfinding and postal counters, 1968 to 1989. Railway station signage, post office
forms, the graphic systems built so that a stranger in a station finds the right platform without
reading a paragraph: one signal colour, big sans type with a tall x-height, flat pictograms,
numbered routes, date stamps, a board that updates one cell at a time.

A letter is a journey through a system the visitor does not know, and the desk is the counter where
someone shows them the route. That is the whole design: a board that says where you are, a paper
with the evidence marked on it, and a numbered route out.

Not a dashboard, not an inbox, not a chat. There is one letter, one deadline and one route.

## Type

- Board and display: **Overpass** (600, 700, 800). Road-sign lineage, tall x-height, tabular
  figures. Every amount, date and reference is set in it.
- Reading and interface: **Atkinson Hyperlegible Next** (400, 600, 700). Drawn for low-vision
  readers, with letterforms that stay distinct at small sizes, which is exactly this audience.
- Script companions, loaded only for the language in use, and used for headings in that script
  rather than falling back to a Latin display face: **Vazirmatn** (Arabic, Farsi), **Noto Sans
  Hebrew** (Hebrew), **Noto Sans** (Cyrillic for Ukrainian and Russian), **Noto Sans SC**
  (Chinese).
- Body text is at least 16px, 45 to 75 characters per line, line height 1.5 in reading columns and
  1.6 in Arabic and Farsi.
- `font-variant-numeric: tabular-nums` everywhere a number can change: the board, the findings
  list, the card.
- Numbers, dates, currency and URLs inside a right-to-left paragraph are wrapped in `<bdi>` so the
  bidirectional algorithm cannot reorder them. This is not optional polish; without it an amount
  reads back wrong to the person who most needs it right.

## Colour

| Token | Light | Dark | Where it is allowed |
|---|---|---|---|
| Signal yellow | `#F5C400` | `#F5C400` | The board, the card header, the landing spine. Nothing else. |
| Ink | `#14213D` | `#F8FAFC` | All text, borders, pictograms. |
| Reading surface | `#FFFFFF` | `#0F172A` | Every surface where the two languages sit. |
| Field | `#EEF0F5` | `#1B2540` | The counter behind the photographed letter. |
| Bar | `#14213D` | `#060B18` | Header and footer bars and numbered chips, in both themes. |
| Rule | `#14213D` | `#3B4A6B` | Borders and dividers. |
| Overdue | `#C8102E` | `#FF6B7A` | Urgency only. |
| Due soon | `#B45309` | `#F2A93B` | Urgency only. |
| Ample time | `#0B7A4B` | `#3DD68C` | Urgency only. |
| Route | `#1F4FBF` | `#7FA5FF` | Links and the one primary action. |
| Quiet | `#4B5670` | `#9FB0CC` | Labels and secondary lines. |

Yellow is dominant but confined: it is the board, never a page background. No gradients, no glass,
no tint layers. The dark theme keeps the same yellow as the only warm colour and lifts the urgency
accents one step so contrast holds.

**Urgency is never colour alone.** Each state carries a word and its own treatment: `Overdue` is
solid, `Due soon` is a diagonal hatch on a pale ground, `Ample time` is outlined. The hatch is what
survives a black and white desk printer, which is where this product ends up.

## Structure: the console

One screen, read like a counter, top to bottom and left to right. No tabs, no sidebar, no cards.

1. **The counter bar.** Where you are: the product, the desk, the library, the volunteer.
2. **The board.** Full width, signal yellow, five cells divided by ink rules: LETTER (sender and
   type), AMOUNT, DEADLINE (with the safe posting date under it), DAYS LEFT (inverted to ink, with
   the urgency word), STATUS (how many facts were checked and how many could not be read). Cells
   fill in one at a time as the reading arrives. An empty cell shows a short dash, never a spinner.
3. **The letter, left.** The photograph as taken, large, slightly off square, with a hard shadow so
   it reads as paper on a counter. Every fact that was used is drawn onto the passage it came from:
   an ink outline with a yellow wash and a numbered ink tab. A passage that could not be read gets a
   dashed outline and the word `unclear`, never a guess.
4. **The findings, right, above the reading.** The facts in the order they stand in the letter, one
   per row, each row a fixed minimum height so an arriving fact never makes the page jump. Each
   carries the number of its mark on the letter. Anything unreadable gets its own row saying so and
   what to ask the visitor.
5. **The route card, right.** Two equal columns, Dutch and the visitor's language, with the
   visitor's column mirrored for right-to-left scripts so it sits where it reads first. The same
   four headings in both: what this is, by when, what happens if you do nothing, what to do now.
   The steps are numbered in ink squares, and the numbers match the marks on the letter, so the
   paper and the plan share one numbering system.
6. **The draft drawer.** The reply or objection in Dutch with the translation beside it, editable,
   the addressee and the official channel printed above it.
7. **The footer bar.** Print desk card (the one primary action, in yellow), Save reminder, Edit
   draft, New letter, and the consent switch with one plain sentence about what is kept.

## Structure: the landing page

A yellow spine runs the full height of the page carrying the section names, and each section is a
band separated by a heavy ink rule. Not a hero with sections under it.

1. **The card.** Opens with the thing the visitor takes home, photographed on a counter, and one
   sentence: every date and amount on it comes from the letter and is checked before it prints.
2. **One session.** Four numbered frames of a single real session, side by side in one band: the
   letter, the board filling, the route, the printed card. Captions in plain English.
3. **Who it is for.** The help desks, a volunteer's own words, and the languages listed in their own
   scripts.
4. **Privacy, as a retention ledger.** A four-column table: what enters, why, who sees it, when it
   is gone. A promise nobody can check is worth less than a table anybody can.
5. **Try it.** The console and the sample letters, with the sample letters named as invented.

## Motion grammar

Things arrive the way a board updates, not the way a web page animates.

- A new board cell or finding row **flips in place** from the edge it belongs to, 180ms, ease-out.
  Nothing fades up from below and nothing scales.
- A highlight on the letter **wipes** across the passage in the reading direction, 220ms.
- The days-left number **counts to its value once** and settles, with no bounce and no easing
  overshoot.
- Rows and cells are reserved at their final height before content arrives, so nothing reflows.
- `prefers-reduced-motion: reduce` removes all of it. Content appears at once, in place.

## Print: the desk card

One A4 sheet, and it must survive a black and white desk printer.

- The yellow header band prints as a solid grey band; sender, letter type, total amount and
  reference sit in it.
- Below it the deadline band, hatched for due soon, carrying the deadline, the days left, the safe
  posting date and a stamped final date.
- Then an identity line: sender, letter type, reference.
- Then the paired rows: Dutch on the left and the visitor's language on the right, question by
  question on the same line, so both readers look at the same thing at the same time.
- Then the numbered actions, both languages on one row each, with the official route in bold.
- The footer carries the referral point in both languages, a space for the volunteer's handwritten
  notes, the calendar reminder filename, and the line that this explains letters and is not legal
  advice.

## Real media

The pages are carried by photographs of the real thing, never by decoration.

- The synthetic sample letters printed on real paper and photographed on a real counter, including
  crooked, shadowed and creased frames, because that is what a phone photo of a letter looks like.
- The printed desk card photographed on the counter and in a hand.
- Real frames of a real session for the landing sequence, not composites.
- Typographic specimens of the supported scripts, set in the faces above.

No illustration, no abstract shapes, no gradient orbs, no stock people, no fake device silhouettes.
Until the photographs exist, the mockups carry captioned placeholders that say exactly which
photograph belongs there.

## Accessibility floors

- WCAG 2.1 AA on contrast, visible focus, keyboard operation and alt text, in both themes.
- Focus is a 3px ink outline with a 2px offset, and on yellow it inverts to white.
- Every urgency state is legible in greyscale and to a colour-blind reader, by word and treatment.
- Right-to-left is a first-class layout, not a mirrored afterthought: logical properties
  throughout, and the printed page is tested in Arabic and Hebrew, not only the screen.
- Touch targets at the desk are at least 44px, since this runs on a tablet at a counter.

## Guard rails

Yellow never becomes a page background. Reading surfaces stay white or ink. No card grids, no
hero-then-sections flow, no rounded corners on structural elements, no drop shadows except the one
that makes paper read as paper, no emoji as icons, no gradients, no glass, no purple, no display
serif. Copy is active voice, real verbs on buttons, errors that explain rather than apologise, and
no dashes longer than a hyphen anywhere.
