# Examples

Two readings captured from the deployed agent, exactly as it answered. Nothing here was edited
after it came back.

Both were read on 2026-09-14 through the hosted console at
<https://plainletter-web.vercel.app/desk>, which sends the letter to the agent on Amazon Bedrock
AgentCore Runtime in Frankfurt (`eu-central-1`), where Claude Sonnet 4.6 does the reading through
the EU inference profile. Each letter went in as a text file, the visitor's language was Ukrainian,
no reading day was pinned, and consent was not given, so nothing was kept (`"case": null`). Both
letters are synthetic: they say so in their own last line, and every name, address and number in
them belongs to nobody.

## Open them with nothing installed

- `desk-card.html` is the card the desk prints. Open it in any browser. It is a single
  self-contained file with no network requests.
- `reminder.ics` is the calendar reminder. Open it with any calendar app, or read it as text.
- `reading.json` is the agent's final answer: every fact with the passage it was taken from, what
  the check grounded, the explanations in both languages, the steps, the draft, and the card and
  reminder above as strings.
- `event-stream.txt` is the answer as it arrived, one `data:` line per stage, in the order the desk
  shows them.
- `letter.txt` is the letter that was sent.

## `traffic-fine/`

A speeding fine from the fine collection agency: EUR 174,00, to be paid before 15 September 2026.
Read at 13:54 UTC in 50 seconds.

All eleven facts the reading extracted were grounded in the letter, with no issue. The deadline
reads one day left, which was true on the day it was read. The desk found the verified sender in
its knowledge base, wrote the steps with official routes, and drafted an appeal to the public
prosecutor, since the letter offers that route.

## `unreadable-reference/`

A municipal parking-tax reminder where two things on the page cannot be read: part of the
assessment number (`4471 [onleesbaar] 6`) and part of the number plate. Read at 13:55 UTC in 60
seconds.

This is the case the product is built around. The reading does not complete either number from
the shape of the gap. It lists both under `unreadable`, each with the question to put to the
visitor, and the card shows the assessment number with its gap intact and a broken key beside the
number plate instead of a value. The ten facts the letter does show were grounded as usual, so the
amount, the deadline and the objection route still reach the card.

One wording slip is visible in the answer: the reason for each unreadable field says the part is
unreadable "in de foto", in the photo, although this letter arrived as text with the gaps typed in.
The fields and the refusal to guess are right. The sentence around them assumed the usual case.

The capture also shows something the desk should not do yet. The payment step, the objection
draft, the card and the reminder still quote the assessment number with its gap,
`4471 [onleesbaar] 6`, so a volunteer has to read the full number off the letter before anything is
paid or sent. Holding those steps until the number is confirmed is
[issue #34](https://github.com/voyagi/plainletter/issues/34).

## `demo-transcript.md`

The narration of the demo video as it is spoken.
