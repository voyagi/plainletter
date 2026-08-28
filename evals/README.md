# The evaluation set

Twenty-two letters, each with the properties a correct reading of it has to show. It exists so that
a change to one of the prompts can be measured instead of argued about.

Nothing in here is part of the product. It is not in the wheel and it is not in the deployed
runtime, because it is the instrument the prompts are measured with rather than something a visitor
ever touches.

## Running it

The run reads every letter with a real model on Amazon Bedrock and costs money on the account whose
credentials are in the environment, so it does not start unless it is asked for:

```sh
PLAINLETTER_EVAL=1 uv run python -m evals.run --json out/eval-before.json
```

Each letter costs one model turn for reading, one for explaining, one for planning and one for
drafting, plus a turn whenever the planner or drafter looks up an official route, and another
whenever the guard sends an answer back to be written again. `--only <slug>` runs one letter, and
is repeatable.

Then change a prompt, run it again into a second file, and compare the two. Comparing reads no
letters and calls no model:

```sh
uv run python -m evals.run --compare out/eval-before.json out/eval-after.json
```

## What a score means, and what it does not

**Read the letters line, not the property ratio.** A letter is correct only when it was read at all
and answered every question it asks. Every letter here is one the desk should be able to read, so a
refusal is always a finding and never a possible right answer. The property count has a floor well
above zero for a reason that is not flattering: several letters assert that there is no deadline and
no amount, and an answer containing nothing satisfies those. Measured on this corpus with
`uv run pytest tests/test_eval_runner.py`, a stand-in that returns an empty reading for every letter
scores **72 of 253 properties and 0 of 22 letters**.

**Twenty-two letters read once each is a sample, not a verdict.** One letter changing side moves the
headline by five points. The comparison above prints which letters changed rather than the
difference between two numbers, because two improving and two getting worse is the same headline as
nothing happening at all. Treat a single letter changing side as noise until it does it twice.

**Watch the guard line before the score.** A prompt that starts inventing dates does not have to
produce a wrong reading: the grounding guard denies the tool call carrying the invented date, the
model writes again, and the answer that reaches the desk is perfect. Scoring only the finished
reading would call that no change at all. So the tool trail is read after every letter and the
denials are counted. They fail nothing, because nobody was harmed, but a version that needs the
guard twice as often has got worse, and this is where that shows first.

**A forbidden string reaching the desk is not a percentage.** Those checks are counted apart and
named. One of them failing is a reason to stop, not a number to weigh against the others.

**Nothing that did not run is reported as clean.** No letters read, or every letter ending in a
harness error, prints UNKNOWN and exits non-zero. Lapsed credentials fail all twenty-two
identically, and nought out of twenty-two would read as a model that answered everything wrong.

## What it does not cover

- **Four of the five prompts.** Every letter here is text, so `transcribe` is never called: the
  pipeline only transcribes pages that arrive as pictures. Reading, explaining, planning and
  drafting are exercised; transcription is not.
- **The live model.** As of 2026-08-28 nothing here has run against Bedrock. The harness is proven
  offline instead, by the tests in `tests/test_eval_corpus.py`, `tests/test_eval_scoring.py` and
  `tests/test_eval_runner.py`, which read every letter with stand-in models that answer badly on
  purpose and require the scorecard to say so.
- **Flakiness.** One run is one sample of a model that does not answer identically twice. Running
  every letter twice doubles the bill, so the honest thing is to say that a single run cannot
  measure it.

## Writing a case

A letter is `<slug>.txt` and its expectations are `<slug>.expected.yaml` beside it. Every letter
says in its own last line that it is invented, and every name, address, citizen service number and
reference number in it belongs to nobody.

An expectation is written down only when the letter itself settles it. **A key that is absent is not
an expectation of nothing.** Leaving `deadline` out means this letter does not settle the question;
writing `deadline: null` means it settles it and the answer is that there is none. The two are told
apart by which keys the file carried, so the difference is real and not a convention.

`what_it_tests` is required and is not decoration. A case nobody can explain is a case nobody will
maintain, and it is the first thing that should go when the set is trimmed.

Two checks apply to every letter without being written in any file: the reading has to be explained
in Dutch and in the visitor's language, and it has to produce at least one step. An empty action
plan is a valid shape and a useless answer, and every other check can pass on one.

The corpus checks itself on every commit. An expected date has to stand on the page in one of the
two ways a Dutch letter writes one, an expected amount has to be printed, a reference has to be
there in digits, and the derived properties are recomputed and compared. A case that asserts nothing
is refused outright.
