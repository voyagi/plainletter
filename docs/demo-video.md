# Demo video: script and shot list

Four minutes twenty at a normal reading pace, inside the five minute limit with room to breathe.
Screen recording plus voiceover, no camera. Every number and date on screen comes from a synthetic
letter shipped in this repository, so nothing real is shown.

## Before recording

1. `uv sync --group dev`, then `npm install`, then `npm run dev --workspace @plainletter/web`.
2. Point the console at a runtime: either `uv run plainletter-serve` in a second terminal, or set
   `PLAINLETTER_AGENT_RUNTIME_ARN` for the deployed one. The deployed one is worth the extra step:
   the stage timings look like the real thing.
3. Print `src/plainletter/samples/cjib-verkeersboete.txt` and
   `src/plainletter/samples/zorgverzekeraar-premieachterstand.txt` on paper. Photograph the first
   one flat and the second one crooked, in a shadow, with a fold across it. The crooked one is the
   point of shot 5.
4. Set the display to light theme, 1440 by 900, browser chrome hidden, and clear the console.
5. Open `docs/architecture.png` in a second tab, ready for shot 6.

## The script

### 1. The problem, 0:00 to 0:22

**On screen:** the photographed letter, full frame, scrolling slowly. No interface yet.

> Every country sends its residents letters they cannot read. This one demands two hundred and
> thirty one euro, gives a deadline, and says what happens if that deadline passes. If you moved
> here last year, or you are eighty, or you read the language slowly, this envelope is a closed
> door with a clock running behind it.

### 2. Who it is for, 0:22 to 0:45

**On screen:** the console at rest, empty, with the intake open. Nothing clicked yet.

> Most countries answer this the same way: a free help desk, usually in a library, where a
> volunteer sits down with you and your letter. The Netherlands runs eight hundred and sixty one of
> them. The first ten minutes at that desk decide everything. What is this. How bad is it. What
> happens if I do nothing. What exactly do I do, and by when.
>
> Plainletter is the agent behind that desk.

### 3. The reading, 0:45 to 2:15

**On screen:** drop the flat photograph on the intake, pick Ukrainian, press the button. Do not cut
away while it works. Let the stages arrive.

> The volunteer photographs the letter and picks the visitor's language.
>
> The picture is straightened, trimmed and stripped of the location the phone recorded, and nothing
> is written to disk. Because this arrived as a photograph, one turn types the letter out, and a
> second, separate turn pulls out the facts. The facts are then checked against the transcript the
> other turn wrote, so a value the extractor invented has to also turn up in a transcription
> written without it.

**On screen:** the marks appear on the letter, numbered down the margin.

> Everything that checked out is marked on the letter itself, and numbered. That numeral is the
> same numeral in the findings, in both explanations, and at the foot of the printed card, so the
> volunteer can say "number four" and the visitor looks at the same words.

**On screen:** the deadline line, then the two explanation columns side by side.

> Fifteen days left, and the last day a posted reply still arrives is the eighth. Then the letter in
> plain language, in Dutch for the volunteer and in Ukrainian for the visitor, answering three
> things: what this is, by when, and what happens if nothing is done.

**On screen:** the steps, then the draft.

> The steps carry official routes, and each route was fetched from a knowledge base through a tool
> call rather than remembered by a model. Then the objection letter itself, in both languages, so
> the visitor knows what they are signing.

### 4. What the visitor takes home, 2:15 to 2:40

**On screen:** press Print the card. Show the A4 sheet in the print preview, in black and white.
Then the calendar file opening with its reminder.

> One sheet, two languages, in the monochrome a library printer actually has. The marks are keyed
> at the foot against the words they were drawn under. And a calendar reminder for the deadline,
> with an alarm three days ahead of it.

### 5. The refusal, 2:40 to 3:20

**On screen:** the crooked, shadowed, folded photograph. Drop it on the intake, pick Polish.

**This shot is the product.** Do not cut it short and do not retake it until it succeeds.

> This one is a real photograph of a real piece of paper: crooked, in shadow, with a fold across a
> line.
>
> The transcription turn could not read one line and said so instead of guessing. The check then
> refused the fact that line carried. There is no number in the margin next to it, because there is
> no fact. The desk card says what to ask the visitor, no draft is written at all, and the reading
> is handed to a person, with the phone number on the card.
>
> That is the whole design. A refused reading at a help desk is recoverable. A confident wrong
> deadline is not.

### 6. How it holds, 3:20 to 4:00

**On screen:** `docs/architecture.png`, panning slowly down the spine.

> Five of these stages are a model speaking, and they are the highlighted ones. Everything else is
> ordinary Python that never calls a model, including the check that decides whether the reading is
> allowed to reach a person.
>
> Every structured answer the model gives is a Strands tool call, and every stage after the check
> runs with an intervention on that boundary. A date or an amount the check did not ground is
> refused before it exists, the refusal goes back to the model as the tool's result, and the model
> writes again. The pipeline then re-reads everything that came through and refuses the whole
> reading if a stray value survived anyway.
>
> It runs on AgentCore Runtime in Frankfurt against Bedrock in the EU. Every prompt and answer in
> the traces reads REDACTED, because the agent pins that policy in code before its first agent
> exists.

### 7. Why it matters, 4:00 to 4:20

**On screen:** the desk card in a hand, or flat on the counter.

> Nothing here is remembered unless the visitor asks for it, and then only checked, masked values
> for thirty days. No name, no letter, no identity number.
>
> The person walks out with the letter, a sheet they can read, and a date in their phone. That is
> the whole job.

## Shot checklist

- [ ] The letter fills the frame before any interface appears
- [ ] The word Plainletter is not said before the problem is stated
- [ ] No Dutch acronym is spoken or shown before 0:22
- [ ] The stages stream in real time, uncut, at least once
- [ ] The marks and the numerals are legible at 1080p
- [ ] The refusal shot shows the gap in the margin, not just the text
- [ ] The printed card is shown in black and white, at page proportions
- [ ] The architecture diagram is on screen while the guard is described
- [ ] Total runtime under five minutes
- [ ] Uploaded public, not unlisted, on YouTube or Vimeo
