# Art direction

Locked 2026-08-21, second attempt. Round one is kept at `ART-DIRECTION-retired.md` with the reason
it failed. Every page, component and line of copy derives from this document. If a screen disagrees
with this file, the screen is wrong. Mockups of the three key surfaces live in `design/mockups/` and
their renders in `design/screenshots/`.

## 0. Who this is for, and what they already look at

This direction is derived from the audience, not from a period or a mood. The evidence was read out
of the live stylesheets of the services these people open every week, on 2026-08-21.

| Service | What it actually serves | What it tells us |
| --- | --- | --- |
| `rijksoverheid.nl` | Rijks Sans and RO Serif, navy `#154273`, yellow `#ffb612`, blue `#01689b`, `border-radius: 0` in 22 declarations | This is the face of the letter that frightens the visitor. Square, navy, yellow |
| `digid.nl` | RO Sans, orange `#e17000`, grey `#5a5a5a` | The same house style, on the login every one of them needs |
| `belastingdienst.nl` | The same RO fonts over a slate ramp `#f1f5f9` to `#050914` | Officialdom is cool, grey and uniform |
| `bibliotheek.nl`, the public library the desk stands in | TheMix, a humanist face, warm near-black `#39373a`, peach `#fde5d0`, orange `#ff7320`, radii of 8px (48 uses), 16px (16), 30px (9) | The room this product lives in is warm, rounded and human |

**The finding that decides everything below: this product belongs to the library, not to the
ministry.** A visitor puts down a letter that scares them. If the screen that explains it carries
the same navy, the same yellow and the same square corners as the letter, it reads as more of the
same institution rather than as help. Round one made exactly that mistake, and it is why colour and
shape here are pulled toward the library counter and away from the government.

The second finding, from the people rather than the pixels: the reader may have low vision, low
literacy, or no Dutch at all, and the volunteer beside them is a retired person or a librarian
rather than a lawyer. Every choice below is judged on whether those two can point at the same thing
and agree what it says.

## 1. Anchor

**The marked-up letter. How one person marks a document by hand to explain it to another.**

Not a period and not a place. The anchor is an ordinary practice everybody has been on both sides
of: someone takes your paper, draws a line under the sentence that matters, writes a number in the
margin, and writes what it means beside it. A highlighter, a number, a note in the margin, and the
original still there underneath so you can check.

Why it belongs to this product and nothing else. Plainletter's one sharp claim is that nothing
reaches the visitor unless it stands in their letter, and that they can be shown where. The
software already works this way: a deterministic verifier grounds every date and amount to the
passage it came from and refuses the reading when it cannot. So the product's guarantee and its
visual system are the same act. Mark the passage, number the mark, say what it means beside it,
and refuse to mark what you could not find.

This cannot be lifted onto a dependency triage tool or an incident timeline, which is the test round
one failed. Both of those have system states and no source document. Take the letter away and this
entire design has nothing to annotate.

## 2. The colour law

**One hue exists in this product, and it may only ever touch words.**

The mark is a highlighter. It sits behind a run of words on the letter, behind the fact that run
produced, and at full strength on the deadline, which is simply the most urgent instance of the same
idea. Everything else is ink on paper: the wordmark, the navigation, the rules, the buttons, the
tables, the chrome. A button is filled with ink, never with the hue.

**Where the hue is forbidden:** a page or panel background, a header or footer bar, a button, a
badge, a card, a logo, an icon, and anything that distinguishes one language from another. The
moment colour fills a region it stops meaning "this came from your paper" and becomes decoration,
which is the round-one failure in one sentence.

| Token | Light | Dark | Where it is allowed |
| --- | --- | --- | --- |
| Desk | `#EFEAE6` | `#191614` | The page ground, the counter the paper lies on |
| Paper | `#FFFFFF` | `#221E1C` | Every reading surface |
| Ink | `#221E1C` | `#F5F1ED` | All text, rules, marks and pictograms |
| Ink 2 | `#5C534E` | `#BDB2AB` | Secondary lines, captions |
| Ink 3 | `#847871` | `#8E827A` | Labels and axis annotations only, never body text |
| Rule | `#DCD4CE` | `#3A3330` | Borders and dividers |
| Mark ink | `#B01E4B` | `#FF8FAE` | The deadline, the key numbers, a mark's own rule |
| Mark wash | `#FFDDE7` | `#4A1626` | Behind a run of words, never behind a region |

Contrast is measured before this ships, not asserted. Ink on Paper, Ink on Desk, Ink 2 on Paper and
Mark ink on Paper each reach at least 4.5 to 1 at text size. Ink on Mark wash reaches at least 4.5
to 1, because the wash always has words on top of it. Ink 3 is never used for anything a person has
to read.

**Urgency is never the hue on its own.** It is a ladder of treatment, so it survives the black and
white desk printer this product ends up on: `Ample time` is plain, `Due soon` carries a hatched
underline, `Overdue` carries a struck rule and a stamped date. Each state also carries its word.

## 3. Type

Two Latin families, both free and self hosted at build time, plus one companion per script. Never
Inter, Roboto, a system stack or Space Grotesk, and none of Sora, Chivo Mono, Funnel Display,
Figtree, JetBrains Mono or Overpass, all of which are spent on sibling products.

| Role | Face | Why this audience specifically |
| --- | --- | --- |
| Working surface: body, findings, controls, the printed card | **Atkinson Hyperlegible Next** (OFL), `wght 200..800` | Drawn by the Braille Institute so that letterforms which normally collapse into each other stay distinct: `I` against `l` against `1`, `O` against `0`. The reader here may have low vision, may be reading a second alphabet, and is looking at a reference number they must copy exactly. No other free face is designed for that job |
| Brand layer only: the wordmark, the one big sentence, landing headlines | **Bricolage Grotesque** (OFL), `opsz 12..96`, `wdth 75..100`, `wght 200..800` | One warm, contemporary voice so the page is not faceless. It is drawn in 2023 and reads as made this year, which is the point after a direction that read as a museum |
| Arabic | **Noto Sans Arabic** (OFL) | Drawn for Arabic. See the rule under this table |
| Farsi | **Vazirmatn** (OFL) | Its own project calls it "a Persian/Arabic font project", Persian first, which is exactly right here and exactly wrong for Arabic |
| Hebrew | **Noto Sans Hebrew** | |
| Cyrillic, Chinese | **Noto Sans**, **Noto Sans SC** | |

**Every script gets a face designed for that script, never one that merely covers it.** Persian and
Arabic share an alphabet but not the letter shapes their readers expect, so a Persian-first family
set in Arabic reads subtly foreign to the one person in the room who most needs it to read right.
The same rule forbids solving Hebrew or Cyrillic with a Latin family that happens to include the
glyphs.

The Latin face must be loaded with **`latin-ext` as well as `latin`**. Polish and Turkish are two of
the twelve visitor languages and their letters live in the extended subset. Loading `latin` alone
drops the l with stroke and the dotless i out of the face mid-sentence, which is the same class of
failure as a mistranslated amount: the visitor sees something that is not their language.

Every family named here was confirmed resolving from the Google Fonts `css2` endpoint on
2026-08-21, and each was checked for the subset it actually serves rather than the one it is
assumed to serve.

**The brand layer never touches the working surface.** Bricolage appears on the wordmark, on the one
plain sentence that opens a reading, and on landing headlines. It never appears on a control, in a
table, in the findings list, on the printed card, or below 24px. If a face is doing the work of
making this design interesting, the design is not interesting enough yet.

Scale, in px: 12 label, 14 caption, 16 body, 17 reading column, 20 lede, 24 section, 30 sentence,
clamp(34, 4.4vw, 56) landing headline. Body never drops below 16px, reading columns hold 45 to 75
characters, line height is 1.55 in Latin and 1.7 in Arabic and Farsi. Uppercase is for short labels
only and never for anything a visitor reads.

`font-variant-numeric: tabular-nums` everywhere a number can change. Numbers, dates, currency and
URLs inside a right-to-left paragraph are wrapped in `<bdi>`, because without it the bidirectional
algorithm reorders an amount and hands the wrong number to the person who most needs it right.

## 4. The one mechanism: the mark and its key

Every fact the reading grounds gets a number. That number appears in exactly four places, and they
are the same number every time:

1. On the letter, as a highlighter wash under the passage, with the numeral in the margin beside it.
2. In the findings list, against the value that passage produced.
3. In both explanations, at the end of the sentence that uses it.
4. At the foot of the printed card, against the quoted passage.

One numbering system across the screen and the paper, in both languages. The volunteer says "number
four" and the visitor looks at the same words, whichever alphabet they are reading.

**A refusal breaks the key.** When the verifier could not ground something, there is no number and
no wash. The margin rule is broken with a gap, and the row reads `Not in the letter` plus what to
ask the visitor. The product's most important behaviour is a structural absence, not a warning
colour, because a colour can be misread and a missing number cannot be mistaken for a fact.

**The key gutter** carries those numerals in a narrow column between the Dutch and the visitor's
text, so neither language owns them and both point at the same mark.

## 5. Structure: the console

One continuous reading surface. No dashboard, no metric row, no tabs, no sidebar, no cards.

1. **A quiet utility line.** Wordmark, the language pair with a swap control, the privacy timer
   saying how long this stays in memory, and `Clear letter`. Ink only. Nothing measured lives here.
2. **The sentence.** One large plain sentence in the visitor's language with the Dutch directly
   beneath it, both in the brand face: what this letter is, the amount, and the date. This is the
   first thing a frightened person reads, and it is a sentence rather than five tiles because
   nobody arrives wanting a dashboard of their own fine.
3. **The deadline line.** Directly under the sentence, in mark ink at full strength: the date, the
   days left, the last safe day to post, and the urgency word with its treatment. One line.
4. **The letter and the reading, side by side on one surface.** Left, the letter as photographed,
   large and slightly off square, every used passage washed and numbered in the margin. Right, the
   reading in a fixed order that never changes between letters: what this is, the amounts, what
   happens if nothing is done, the numbered actions with their official routes, and last, what could
   not be verified.
5. **The two languages are equal.** Same width, same weight, same position in the order. Each
   controls its own direction, and a right-to-left column aligns right without mirroring the
   amounts, the key numerals or the letter itself. The key gutter runs between them.
6. **The draft, when there is one.** The reply or objection in Dutch with the translation beside it,
   editable, addressee and channel printed above it. When no letter is needed, the space says so.
7. **A persistent action line.** `Print the card`, `Add the reminder`, `New letter`. Ink filled.

## 6. Structure: the landing page

The page is a marked-up letter. It explains the product by doing the product, on one real synthetic
letter, and it never becomes a hero followed by feature cards.

1. **You open inside the letter.** The wordmark and one line, `Put the letter down. Leave knowing
   what to do.`, sit in the letter's own margin rather than in a separate hero band.
2. **Scrolling walks the marks.** Passage by passage down one real letter, each mark's meaning
   arriving in the margin beside it, in Dutch and in Arabic. What the product does is stated at the
   moment it is proved, never as a claim in its own box.
3. **The refusal gets its own mark.** One passage on that letter could not be grounded, and the page
   shows the broken key and the words the desk would say instead. It is the most important thing
   here and it is shown, not asserted.
4. **Privacy is a retention ledger** in the margin: what enters, why, who sees it, when it is gone.
   A promise nobody can check is worth less than a table anybody can.
5. **The card, flat, at real proportions,** in monochrome as it actually prints, followed by one
   institutional ask: `Bring Plainletter to your library`. Not a signup box.

## 7. At 390px, where half the visitors are

The columns do not become tabs and no language is hidden behind a control. The reading interleaves,
one numbered unit at a time: the visitor's language first, the Dutch beneath it, then the shared key
line. The visitor's language leads because the phone in this scenario is usually theirs.

The letter becomes a full-width strip that opens to the cited passage when a key numeral is tapped,
and the key gutter turns ninety degrees into a full-width numbered rule. The order of the reading is
identical to the desktop, because a person who used it at the desk should recognise it at home.

## 8. Motion grammar

Marking, not animating. A mark is made by a hand, so it arrives the way a hand makes it.

- A highlighter wash **wipes across its passage in the reading direction**, 220ms, ease-out, with
  the wash's round cap leading. Right-to-left passages wipe right to left.
- A finding row and its numeral appear together, 140ms, no fade from below and no scale.
- The days-left numeral **counts once to its value** and settles, no bounce.
- Every row and cell is reserved at its final height before content arrives, so nothing reflows
  under a reader's eye.
- Nothing animates because it scrolled into view. Nothing loops.
- `prefers-reduced-motion: reduce` removes all of it: washes paint at full extent, rows appear in
  place, the numeral prints its value.

## 9. Print: the desk card

One A4 sheet that must survive a black and white desk printer at a library counter.

- A ruled head carries the sender, the letter type, the total and the reference.
- The deadline band beneath it carries the date, the days left, the last safe posting day, and the
  urgency word with its treatment. Hatch and struck rule survive greyscale, the hue does not.
- Paired rows: Dutch left, the visitor's language right, question by question on one line, so both
  readers look at the same thing at the same time.
- The numbered actions, both languages on one row each, official route in bold.
- The key at the foot: each numeral against the passage it marked, quoted from the letter.
- A ruled box for the volunteer's handwritten notes, the referral point in both languages, the
  reminder filename, and the line that this explains letters and is not legal advice.

## 10. Real media

The pages are carried by the product's own artifacts at full size. The letter is the image.

1. **The twelve synthetic letters**, really marked up, shown as documents rather than as thumbnails.
2. **The printed card**, flat and at real proportions, in the monochrome it prints in.
3. **Photographs of the real thing**: printed letters on a real counter including crooked, shadowed
   and creased frames, because that is what a phone photo of a letter looks like, and the printed
   card in a hand. Secondary to the documents, never decoration.
4. **Typographic specimens** of the supported scripts, set in the faces above.

No illustration, no abstract shapes, no gradient orbs, no stock people, no device silhouettes. Until
the photographs exist the mockups carry captioned placeholders naming the exact shot, and a
placeholder never occupies the position of the hero.

## 11. Accessibility floors

- WCAG 2.1 AA on contrast, visible focus, keyboard operation and alt text, in both themes.
- Focus is a 3px ink outline at a 2px offset, inverting to Paper over dark surfaces.
- Every urgency state is legible in greyscale and to a colour-blind reader, by word and treatment.
- Right-to-left is a first-class layout: logical properties throughout, and the printed page is
  proofed in Arabic and Hebrew, not only the screen.
- Touch targets are at least 44px, because this runs on a tablet on a counter.
- Body text never below 16px, and the reading columns are set for a reader who is not fluent.

## 12. Why this is not the house style

Checked by name against `workshop\design-registry.md`, which requires a new direction to differ from
every entry on anchor family, palette shape and structure metaphor.

- **Anchor family:** a hand-annotation practice. Not the mid-century operations room of Throughline,
  Ringbolt round one and bumpwarden round one, not Ringbolt's contemporary instrumentation, not
  bumpwarden's discipline of published measurement.
- **Palette shape:** warm paper and ink with exactly one hue that may only ever touch words. Not a
  dark saturated ground with a cream reading surface and signal accents, not a dark deck with a
  multi-hue status set, not a monochrome interface with a risk ramp, and not round one's navy board
  with a signal colour.
- **Structure metaphor:** a primary document with a keyed margin apparatus. Nothing here pretends to
  be a rack, a panel, a board or an instrument.

**Would this direction have suited the previous products?** No. The mark and its key need a source
document the reader can point at. A dependency queue has no document, an incident timeline has no
document, and a call queue has no document. Remove the letter and there is nothing to annotate,
which is the proof that this was derived here rather than borrowed.

## Banned in this product

The hue filling any region. Metric and statistic tiles. Card grids. A hero followed by feature
sections. Language tabs. Navy with yellow, and anything else that reads as the Rijkshuisstijl.
Square-cornered institutional chrome. Gradients, glass, gradient text, nested cards, bounce easing,
anything animating on scroll, emoji as icons, stock photography, device silhouettes, purple or
indigo on white, a display face on the working surface, and placeholder copy of any kind.

No dashes longer than a hyphen anywhere this product prints, on screen or on paper.
