# Runbook

What to do when Plainletter is running and something is wrong. `docs/deploy.md` is how it gets
there; this page is what happens afterwards.

**Read this first.** Every procedure below is written from the deployment code and the AgentCore
CLI's own behaviour, and none of it has yet been rehearsed against a live deployment, because there
has not been one. Where a step has not been performed on real infrastructure, it says so on the
line. That is the difference between a runbook and a wish, and it is worth more to whoever is
holding the pager than a confident page would be.

## What it rests on

Nothing here has a fallback, which is a scope decision rather than an oversight. They do not all
fail the same way, and the column on the right is the one to read during an incident: losing the
model or the runtime stops every reading, while losing the memory store costs only case recall and
readings carry on.

| It depends on | Where | What breaks without it | Owned by |
| --- | --- | --- | --- |
| Amazon Bedrock, `eu.anthropic.claude-sonnet-4-6` | EU inference profile, sourced from `eu-central-1` | Every reading. This is the model that transcribes, reads, explains, plans and drafts | AWS |
| Amazon Bedrock, `eu.anthropic.claude-haiku-4-5` | Same | **Nothing today.** No code path calls it: drafting was its job until the first live letter and moved to Sonnet. The runtime's IAM policy still allows it so that moving a stage back is a settings change rather than a redeploy | AWS |
| AgentCore Runtime | `eu-central-1` | Everything. The agent is the deployment | AWS |
| AgentCore Memory | `eu-central-1` | Consented cases only. A visitor cannot bring a case number back. A reading itself still works and says so | AWS |
| AgentCore Observability, through CloudWatch Transaction Search | `eu-central-1` | Traces. Readings continue and nobody can see how they went | AWS |
| The console host, Vercel or any Node host | Wherever it is deployed | The desk's only screen. The agent is still reachable from a terminal | The host |
| The console's IAM credentials | The host's environment | Every reading through the console, with a signing error rather than a model error | This deployment |

The model ids are pinned in `src/plainletter/bedrock.py` and overridable through
`PLAINLETTER_READING_MODEL` and `PLAINLETTER_DRAFTING_MODEL`. They are aliases rather than dated
ids, because AWS publishes no dated id for this model, so the runtime probes them at startup
instead: `probe_models` asks the region about each configured id before a letter depends on the
answer. It reports three states and they are not the same, which matters when reading a startup
log. The region knows the id. The region says there is no such profile, which is a wrong id or a
model not enabled on the account. Or the account would not answer, which is usually missing
credentials or no network, and is reported without being called a failure.

## Turn the reading service off without taking anything down

The first move in almost every incident, and the one to reach for before anything clever.

```sh
PLAINLETTER_MAX_READINGS_PER_DAY=0
```

**On the runtime, and only there.** That variable is read by the agent (`src/plainletter/settings.py`)
and by nothing else: setting it on the console's host does nothing at all, because the console's own
limits are fixed in `web/src/server/limits.ts`. Set it on the runtime and redeploy. Zero is refused
before the first model call, so spend stops immediately, the deployment stays up, and the pages
still serve. Not rehearsed live; the ceiling itself is covered by tests in `tests/test_spend.py`.

It closes the reading service everywhere, including through the console, because the console has no
other way to read a letter than to call the runtime. If what needs closing is the console itself
(an abusive caller, a broken page), that is an action at its own host: take the deployment down or
pause it there. There is no environment variable in this repository that switches the console off.

Both counters live in the process that serves the request, and say so in their own code. A restart
resets them. That is why the account budget alarm exists and is not optional: it is the only
ceiling a restart cannot clear.

## Roll the code back

There is one artifact and one command, so a rollback is a redeploy of an earlier commit.

```sh
git checkout <the-last-good-commit>
agentcore package
agentcore deploy
```

`package` builds the zip without touching AWS, so a packaging failure costs nothing. `deploy`
updates the same runtime rather than making a second one. Check the result with `agentcore status`
and one `agentcore invoke cjib-verkeersboete`, which reads a synthetic letter end to end. Not
rehearsed live.

The console rolls back through its own host. On Vercel that is promoting the previous deployment,
which does not touch the agent at all: the two halves are deployed separately on purpose, and a bad
console is not a reason to redeploy an agent that is behaving.

## Roll the data back

**There is nothing to roll back, and that is the design.** No letter is written to disk at any
point. The only stored data is a consented case record: derived, masked display values, no letter
text, expiring after thirty days by the store's own rule. There is no backup of it and there will
not be one, because a backup of case records is a copy of vulnerable people's correspondence
metadata sitting somewhere with a longer retention than the thing it copies.

So the data procedures are these, and they are all of them:

- **A visitor asks to be forgotten.** The erasure route removes their case. `docs/privacy-accountability.md`
  holds the rights and the routes; the code is `src/plainletter/memory.py` and the console's
  `/api/forget`.
- **The store is lost or corrupted.** Cases are gone. Readings still work, and a visitor with a case
  number is told the case is not there rather than shown a wrong one. Say so plainly if anybody asks:
  no case record has ever been the only copy of anything, because the letter itself is in the
  visitor's hand.
- **The store must be emptied deliberately.** `agentcore remove all` then `agentcore deploy` rebuilds
  the runtime and the store from nothing. Not rehearsed live.

## Reading the symptom

| What is seen | Most likely | First thing to check |
| --- | --- | --- |
| Every reading fails at once, console and terminal alike | The model, the region, or model access on the account | The startup probe's three states, above. Then the Bedrock console for model access |
| Console fails, `agentcore invoke` works | The console's credentials or its runtime ARN | `PLAINLETTER_AGENT_RUNTIME_ARN` matches `agentcore status`, and the host's IAM user may call `bedrock-agentcore:InvokeAgentRuntime` on that exact ARN |
| Readings refused before anything happens | The daily ceiling was reached, or is set to zero | `PLAINLETTER_MAX_READINGS_PER_DAY` on the runtime |
| One caller blocked, others fine | The console's per-caller meter | `web/src/server/limits.ts`. On a proxied host `PLAINLETTER_TRUST_PROXY_HEADER` must be true, or every caller counts as one and the whole desk shares one allowance |
| Readings work, nothing appears in CloudWatch | Transaction Search was never switched on | The one-time account switch in `docs/deploy.md`, "Before the first deploy", step 5 |
| Consent ticked, no case comes back | No memory store id reached the runtime | `agentcore status` for the store, and `MEMORY_PLAINLETTERMEMORY_ID` on the runtime. Empty means the agent keeps nothing and says so, which is a configuration state and not a bug |
| The bill is climbing with no visitors | Somebody found the public endpoint | Set the ceiling to zero, then read the budget alarm and the console's meter |

## Rotate a credential

- **The console's AWS access key.** Make a new key for the same IAM user, set
  `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` on the host, redeploy the console, confirm one
  reading, then delete the old key in IAM. That order leaves no window where the desk is down.
- **The runtime's execution role.** It carries no key. Permissions are in
  `src/runtime-permissions.json` and are attached by the CDK app; change them there and redeploy.
- **Anything found in the source.** Rotate first, then remove it from the history, in that order. A
  credential in a public repository is public from the moment it is pushed, and this repository goes
  public.

## After an incident

Write down what was affected, what was done, and whether anybody had to be told. If personal data
may have been exposed, `docs/privacy-accountability.md` carries the breach procedure with the 72
hour assessment and the supervisory authority, and it is the page to open before this one.
