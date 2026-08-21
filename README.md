# Plainletter

An agent that reads official letters for the people who help newcomers understand them.

A volunteer at a library help desk, or the person holding the letter, photographs or uploads a
letter from the tax office, the fine collection agency, the municipality, a benefits agency, an
insurer or a debt collector. Plainletter reads it, names the sender and the kind of letter, pulls
out every amount, reference number and deadline, explains the letter in plain language in Dutch
and in the reader's own language, says what happens if nothing is done, lays out the next steps
with the official routes, drafts the reply or objection when that is the right move, says clearly
when a human professional should take over, and prints a one-page desk card the visitor takes home.

Built with the [Strands Agents SDK](https://strandsagents.com/) on Amazon Bedrock, deployed on
Amazon Bedrock AgentCore in the EU (Frankfurt).

## Nothing reaches the visitor that is not in the letter

The reading stage may return anything. What it returns then passes a verifier written in plain
Python that never calls a model: for every date, amount, reference and passage it checks that the
cited text really stands in the letter, and that the claimed value follows from that text. A
deadline whose passage says something else fails, and so does a passage the letter never carried.

Two more things sit behind it. Every stage after the verifier runs with an intervention that denies
any tool call carrying a date or amount the check did not ground. The pipeline then re-reads
everything the model wrote and refuses the whole reading if a stray value survived. A refused
reading at a help desk is recoverable; a confident wrong deadline is not.

The knowledge base marks each sender `verified` or not. Only a sender whose procedure was read on
an official page states a procedure; the rest say so and route the letter to a person.

## What the check runs against

A check is only as good as the text it checks against. A text upload carries the letter's words
already, and a born-digital PDF carries them in its text layer, which is pulled out locally before
any model sees the file. Those readings are checked against the document itself.

A photograph carries no words at all. There, one turn types the letter out and a separate turn
extracts the facts, and the facts are checked against the transcript the other turn produced. A
value the extractor invents has to also turn up in a transcription written without it.

## Where the letter comes in

Photographs arrive sideways and far larger than any model looks at, and they carry the coordinates
of the room they were taken in. Intake applies the orientation the phone recorded, cuts the long
edge to what the reading model actually reads, re-encodes every page so the location metadata is
dropped, and turns a PDF into one picture per page. Nothing is written to disk on the way.

## Run it

```sh
uv sync --group dev
uv run plainletter demo --language ar --out out
```

That reads a synthetic traffic fine end to end with a scripted reading, so it needs no cloud
account, and writes `out/desk-card.html` and `out/reminder.ics`. There are twelve sample letters,
one for every sender in the knowledge base: `uv run plainletter demo --sample` lists them.

```sh
uv run plainletter read letter.jpg --language tr
uv run plainletter-serve
```

`read` takes a photograph, a PDF or a text file and runs the same pipeline against Amazon Bedrock
in `eu-central-1`, which needs credentials. `plainletter-serve` starts the AgentCore runtime
entrypoint on `127.0.0.1:8080`, the same one the deployed service runs, so the console can be
developed against it:

```sh
curl -s localhost:8080/invocations -H 'content-type: application/json' \
  -d '{"sample": "gemeente-parkeerboete"}'
```

```sh
npm run verify:ship
```

is the single gate: types, the full test suite, whole-repo lint, and the committed floors.

## Repository layout

| Path | What lives there |
|---|---|
| `src/plainletter/` | The agent: reading, verification, urgency, planning, rendering |
| `src/plainletter/senders/` | The curated sender knowledge base, one file per sender, sourced and dated |
| `src/plainletter/samples/` | Synthetic sample letters for the demo and the tests (no real people, no real data) |
| `web/` | The desk console and the public landing page |
| `design/` | The committed art direction and the mockups every page derives from |
| `tests/` | Test suite |
| `scripts/` | Repository gates run in the pre-commit hook and in CI |
| `docs/` | Architecture, decisions, privacy notes |

## License

Apache-2.0. See [LICENSE](LICENSE).
