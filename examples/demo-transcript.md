# Demo video transcript

The words spoken in the demo video, one paragraph per shot, in the order they are heard. Every
letter in the video is made up: no real person, address or case appears in it.

Day counts and results are the ones the recorded take showed on 13 September 2026. A reading of a
photograph can come out a little differently each time, so a fresh run may not match the numbers
below line for line.

## The problem

Every country sends people letters they can't read. This one wants a hundred and seventy-four
euros, gives a deadline, and says what happens if you miss it. If you moved here last year, or
you're eighty, or you just read the language slowly... this envelope is a closed door, with a clock
running behind it.

## Who it is for

Most countries answer this the same way: a free help desk, usually in a library, where a volunteer
sits down with you and your letter. The Netherlands has eight hundred and sixty-one of them. And
the first ten minutes at that desk decide everything. What is this? How bad is it? What happens if
I do nothing? What exactly do I do, and by when?

Plainletter is the agent behind that desk.

## The reading

The volunteer takes a photo of the letter, and picks the visitor's language.

The picture gets straightened, trimmed, and stripped of the location the phone recorded. Nothing is
written to disk. Because it came in as a photo, one turn types the letter out, and a second,
separate turn pulls out the facts. Then those facts are checked against the other turn's
transcript. So a value the extractor made up would also have to show up in a transcription written
without it.

Two days left. And the desk works out the last day a posted reply still arrives. Then the letter in
plain language: Dutch for the volunteer, Ukrainian for the visitor. It answers three things. What
this is, by when, and what happens if nothing's done.

Everything that checks out is marked on the letter itself, and numbered. That number is the same in
the findings, in both explanations, and at the bottom of the printed card. So the volunteer can say
"number four", and the visitor looks at the same words.

The steps carry official routes, and each route comes from a knowledge base through a tool call,
not from a model's memory. Then the appeal letter itself, in both languages, so the visitor knows
what they're signing.

## What the visitor takes home

One sheet, two languages, in the black and white a library printer actually has. The marks are
keyed at the bottom, against the words they were drawn under. And there's a calendar reminder for
the deadline, with an alarm three days before it.

## The refusal

This one's a real photo of a real piece of paper. Folded, in shadow, and taken in a hurry, so the
edge runs off the frame.

Two lines on this letter are folded and blurry, so the desk types them as unreadable. And it can't
see what the cut-off right edge says.

Five facts check out. Seven don't, so they never become facts on the card. And there's no number
next to those blurry lines.

That's the whole design. A reading that says it isn't sure can be fixed at the desk. A confident
wrong amount can't.

## How it holds

Five of these stages are a model speaking. They're the highlighted ones. Everything else is
ordinary Python that never calls a model, including the check that decides whether a reading is
allowed to reach a person.

Every structured answer the model gives is a Strands Agents tool call, and every stage after the
check runs with an intervention on that boundary. A date or an amount the check didn't ground is
refused before it exists. The refusal goes back to the model as the tool's result, and the model
writes again.

Then the pipeline re-reads everything that came through, and refuses the whole reading if a stray
value got through anyway.

It runs on AgentCore Runtime in Frankfurt, against Bedrock in the EU. Every prompt and answer in the
traces reads redacted, because the agent pins that policy in code before its first agent even
exists.

## Why it matters

Nothing here is remembered unless the visitor asks. And even then, only checked, masked values, for
thirty days. No name, no letter, no identity number.

The person walks out with their letter, a sheet they can read, and a date in their phone. That's the
whole job.
