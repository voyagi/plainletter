# What the tests actually cover

Measured 2026-08-28. Every number below is the output of the command printed beside it, run that
day on this tree. Nothing here is estimated, and a figure nobody can reproduce does not belong in
this file.

The short version: the agent is covered well, the browser half is covered thinly, and the reasons
are different in each case and stated below rather than averaged into one number that would hide
both.

## The suites

| Suite | Command | Tests | Time |
| --- | --- | --- | --- |
| Agent and scripts, Python | `uv run pytest -q` | 301 passed | 4.9s |
| Console and landing page | `npm run test --workspace @plainletter/web` | 34 passed, 4 files | 1.5s |

Neither suite can reach Amazon Bedrock or spend anything. The model is replaced by a scripted
stand-in (`tests/scripted_strands.py`), so a test that appears to read a letter is exercising the
pipeline, the verifier and the guard against a canned answer, never a live model.

## Line coverage, the agent

`uv run pytest -q --cov=plainletter --cov=scripts --cov-report=term`

**92% of 1,730 statements, 147 missed.**

| Module | Stmts | Miss | Cover | What it is |
| --- | --- | --- | --- | --- |
| `plainletter/schemas.py` | 149 | 0 | 100% | The structured shapes every model answer has to fill |
| `plainletter/locales/__init__.py` | 73 | 0 | 100% | The locale boundary itself |
| `plainletter/demo.py` | 47 | 0 | 100% | The offline demo path |
| `plainletter/spend.py` | 36 | 0 | 100% | The daily reading ceiling |
| `plainletter/text.py` | 32 | 0 | 100% | Text handling below the model |
| `plainletter/urgency.py` | 31 | 0 | 100% | Days left, and the last day a posted reply arrives |
| `plainletter/telemetry.py` | 26 | 0 | 100% | The trace redaction policy |
| `plainletter/tools.py` | 25 | 0 | 100% | The Strands tools the agent may call |
| `plainletter/reading_model.py` | 17 | 0 | 100% | The five prompts |
| `plainletter/settings.py` | 16 | 0 | 100% | Environment reading |
| `plainletter/__init__.py` | 1 | 0 | 100% | Package marker |
| `scripts/__init__.py` | 0 | 0 | 100% | Package marker |
| `plainletter/bedrock.py` | 99 | 1 | 99% | The model calls and the startup probe |
| `plainletter/guard.py` | 44 | 1 | 98% | The intervention that refuses an ungrounded value |
| `plainletter/kb.py` | 82 | 2 | 98% | The knowledge base of senders and official routes |
| `plainletter/locales/nl.py` | 89 | 2 | 98% | Every Dutch fact, behind the boundary |
| `plainletter/marks.py` | 86 | 3 | 97% | The numerals in the margin of the letter |
| `plainletter/pipeline.py` | 112 | 5 | 96% | The stages, in order |
| `plainletter/redact.py` | 20 | 1 | 95% | Masking a citizen service number and an IBAN |
| `plainletter/memory.py` | 103 | 6 | 94% | The consented case store and erasure |
| `plainletter/render.py` | 84 | 5 | 94% | The desk card and the calendar reminder |
| `plainletter/app.py` | 206 | 15 | 93% | The AgentCore entrypoint |
| `plainletter/intake.py` | 132 | 12 | 91% | Photographs, PDFs, and what is refused |
| `plainletter/verify.py` | 111 | 10 | 91% | The check that grounds every date and amount |
| `scripts/export_web_data.py` | 31 | 6 | 81% | Build-time export of sample data for the console |
| `plainletter/cli.py` | 78 | 78 | **0%** | The `plainletter` command line |

**`cli.py` at zero is the one real hole, and it is not a small one.** It is 78 statements of
user-facing surface, it is an installed console script, and no test touches it. Everything it
drives is covered underneath it, so what is unproven is the wiring: argument handling, how a bad
path is reported, what the exit codes are. Written down here rather than left to be discovered by
whoever first runs it.

The rest of the misses are narrow and deliberate: branches that need a real AWS client
(`bedrock.py` line 255), a failure path in the guard, the two knowledge-base lookups that only fire
on an unknown sender, and the error arms of the intake and verifier that need a malformed model
answer to reach.

## Line coverage, the console and landing page

`npm run test:coverage --workspace @plainletter/web` (V8 provider)

| | |
| --- | --- |
| Statements | 25.69% (147 of 572) |
| Branches | 23.7% (101 of 426) |
| Functions | 30.48% (50 of 164) |
| Lines | 25.29% (130 of 514) |

That number is low and the shape of it matters more than the figure:

| Area | Stmts | What it is | Why it reads the way it does |
| --- | --- | --- | --- |
| `src/server/limits.ts` | 96.29% | The metering and the origin check on the one public door | Pure logic, tested directly, and the piece most worth proving |
| `src/lib/language.ts` | 89.47% | Which language a block is written in | Pure logic, tested directly |
| `src/lib/reading.ts` | 84.61% | Reading the streamed stages into state | Pure logic, tested directly |
| `src/components/LetterSheet.tsx` | 100% | The letter with numerals in its margin | Rendered and asserted in `ReadingPanel.test.tsx` |
| `src/components/ReadingPanel.tsx` | 100% | The reading itself, in two languages | Rendered and asserted |
| `src/server/agent.ts` | 0% | The signed call to the deployed runtime | Needs AWS. Exercised only against a real deployment |
| `src/server/caller.ts` | 0% | Identifying a caller behind a proxy | Reachable, and untested. A gap |
| `src/app/api/read/route.ts` | 0% | The public upload endpoint | A gap, and the one that matters most: see below |
| `src/app/api/forget/route.ts` | 0% | The erasure endpoint | A gap |
| `src/components/console/DeskConsole.tsx` | 0% | The console screen, 479 lines | Not unit tested. Checked by hand in a browser |
| `src/components/console/Intake.tsx` | 0% | Upload and camera capture | Not unit tested. Checked by hand in a browser |
| `src/app/page.tsx` | 0% | The landing page | Not unit tested. Checked by hand in a browser |
| `src/app/layout.tsx`, `privacy`, `desk`, `not-found`, `robots`, `sitemap`, `sample-card`, `proxy.ts`, `env.ts` | 0% | Layout, static pages and wiring | Not unit tested |

**The upload route at zero is the gap worth naming twice.** It is the only unauthenticated,
metered path on the public internet, and the logic it enforces is covered: `limits.ts` sits at 96%
with its own tests. What is unproven is that the route calls that logic in the right order and
refuses in the right places. The pieces are tested and their assembly is not.

## What is proven by breaking it on purpose

Line coverage says a line ran. It does not say a test would have noticed if the line were wrong.
Two gates in this repository are held to the stronger standard by harnesses that ship beside them:
each disables exactly one rule and asserts the gate's own self-test goes red.

| Harness | Command | Result |
| --- | --- | --- |
| Client secrets in the built bundle | `node scripts/check-client-secrets.mutants.mjs` | **74 of 74 mutations caught**, no escapes, full sweep |
| Process artifacts in the tracked tree | `node scripts/check-ship-artifacts.mutants.mjs` | **3 of 43 completed, all 3 caught.** Sweep stopped, not finished |

Three of those 74 are new today, and they exist because of a false positive this gate produced on a
real run: it was reading the bundler's own cache and the dev server's output as though a browser
received them. Skipping a tree is exactly the change that can quietly become a false clean, so each
skip has a control, and one of the three mutations widens a skip until it swallows the client
chunks and proves the suite notices.

**The artifacts sweep was stopped rather than completed, and the number above says so.** At the
rate observed on this machine, roughly thirteen minutes a mutation, all 43 would take about nine
hours. Three ran, three were caught, and the honest reading of that is three, not forty-three. It
is worth finishing on a machine that can leave it running.

Nothing in the product itself is mutation tested. There is no Stryker configuration and no score to
quote, so none is quoted.

## What nothing covers yet

- **An evaluation set.** No corpus of letters with expected properties exists, so nothing measures
  whether a change to a prompt made readings better or worse. Twelve synthetic samples in
  `src/plainletter/samples/` are fixtures for the pipeline, not an eval.
- **A committed accessibility gate.** The accessibility figures in this project's records were
  measured by driving a real browser by hand: zero contrast failures in both themes on every route,
  no body text under 16px, one heading per page, no control under 44px, no horizontal scroll at
  390px. Real measurements, and not one of them will run again by itself. A committed gate would.
- **A live deployment.** Nothing here has run against Amazon Bedrock or AgentCore Runtime. The
  three claims in `docs/deploy.md` under "Check the three things" are proven locally against a
  scripted model, a fake store and the local runtime, and are unproven in Frankfurt.
- **A Lighthouse score.** `lighthouse` is not installed, so the composite figure has never been
  produced. Its parts were measured directly, including a 166 kB bundle against a 260 kB budget
  enforced by `npm run gate:size`.
