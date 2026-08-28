# Deploying Plainletter

The agent runs on Amazon Bedrock AgentCore Runtime in Frankfurt (`eu-central-1`), keeps consented
case records in AgentCore Memory in the same region, and sends its traces to AgentCore
Observability. The console runs anywhere Node runs and reaches the agent with a signed call. This
page is the whole procedure. Every command is run from the repository root unless it says otherwise.

## What gets deployed

| Piece | Where | Defined by |
| --- | --- | --- |
| The agent, as a zip of `src/` plus its dependencies built for `arm64` | AgentCore Runtime, `eu-central-1` | `agentcore/agentcore.json`, `src/main.py`, `pyproject.toml` |
| The memory store for consented cases, 30-day expiry, no long-term strategies | AgentCore Memory, `eu-central-1` | `agentcore/agentcore.json` |
| The runtime's execution role, with the model and memory permissions it needs | IAM | `src/runtime-permissions.json`, attached by the CDK app |
| The desk console and landing page | Vercel (or any Node host) | `web/` |

Nothing is deployed outside the EU. The model calls go to the `eu.` cross-region inference
profiles, which are sourced from Frankfurt and stay within EU regions.

## Before the first deploy

1. Install the tools: Node 20 or later, `uv`, and the AgentCore CLI with
   `npm install -g @aws/agentcore`. The CLI packages the Python code with `uv`, so `uv` must be on
   the path.
2. Sign in to AWS in your terminal (`aws login`, or a profile in `~/.aws`). The CLI deploys with
   whatever credentials boto3 and the AWS SDK find.
3. Enable `anthropic.claude-sonnet-4-6` for the account in the Bedrock console. That is the one the
   product calls, for every stage. `anthropic.claude-haiku-4-5` is in the runtime's IAM policy and
   is called by nothing today, so enabling it is optional: do it only if you intend to point
   `PLAINLETTER_DRAFTING_MODEL` back at it.
4. Copy the deployment target and fill in the account id:

   ```sh
   cp agentcore/aws-targets.example.json agentcore/aws-targets.json
   ```

   The real file is ignored by git on purpose. Keep the region `eu-central-1`.
5. Turn on CloudWatch Transaction Search once for the account, so AgentCore Observability can show
   the traces. The switch is in the CloudWatch console under Application Signals, Transaction
   Search, and the AWS guide for it is
   <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html>.

## Deploy the agent

```sh
agentcore validate
agentcore package
agentcore deploy
```

`package` builds `agentcore/plainletter.zip` without touching AWS and is the fast way to see a
packaging problem. `deploy` synthesises a CloudFormation stack with the CDK app in
`agentcore/cdk/`, uploads the zip, and creates the runtime, the memory store and the role. The
first run takes several minutes. Every later `agentcore deploy` updates the same resources.

When it finishes, read back what was made:

```sh
agentcore status
```

Two values from that output matter for the console: the runtime ARN, which looks like
`arn:aws:bedrock-agentcore:eu-central-1:123456789012:runtime/plainletter-xxxxxxxxxx`, and the
memory id. The runtime already knows its memory id: the deployment injects it as the environment
variable `MEMORY_PLAINLETTERMEMORY_ID`, which the agent reads.

Try it once from the command line, with a sample letter, before wiring the console:

```sh
agentcore invoke cjib-verkeersboete
agentcore invoke '{"sample": "cjib-verkeersboete", "today": "2026-08-22", "consent": true}'
```

A bare word is a sample name and a JSON object is the full request. The answer is the finished
reading with the printable card and the calendar reminder in it.

## Wire the console to the deployed agent

The console talks to the agent through `web/src/server/agent.ts`, which runs on the server. Set one
variable where the console runs:

```sh
PLAINLETTER_AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:eu-central-1:123456789012:runtime/plainletter-xxxxxxxxxx
```

With that set, every reading is a signed `InvokeAgentRuntime` call from the host's AWS
credentials. The host needs credentials that may call `bedrock-agentcore:InvokeAgentRuntime` on
that ARN and nothing else: on Vercel, add `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` for an
IAM user or role with exactly that permission as environment variables of the project. The browser
never sees any of it.

Without the variable, the console posts to `PLAINLETTER_AGENT_ENDPOINT` (default
`http://127.0.0.1:8080`), which is the same agent started locally with `uv run plainletter-serve`.

Set one more variable wherever the console is hosted behind a proxy, which includes Vercel and
every managed host:

```sh
PLAINLETTER_TRUST_PROXY_HEADER=true
```

And two more before the console serves a real letter, because the privacy page has to name a real
person or organisation and the code cannot know which one you are:

```sh
PLAINLETTER_CONTROLLER_NAME=Taranity
PLAINLETTER_CONTROLLER_CONTACT=hello@taranity.com
```

Those are the values for the hosted demo. A library running its own copy is the controller of that
copy and sets its own name and contact address here. Left unset, the page says the organisation
running the desk is the controller and tells the visitor to ask at the counter, which is true but is
not the name and address Article 13 asks for.

The upload route meters each caller by the last hop of `X-Forwarded-For`, and that entry is only
trustworthy when a proxy really wrote it. Left unset, every caller is counted as one, so the desk
still works and the ceiling is simply shared. The ceilings themselves are in
`web/src/server/limits.ts`; the agent's own daily ceiling is `PLAINLETTER_MAX_READINGS_PER_DAY`
(default 200, zero closes the service), and neither of them replaces the account budget alarm.

## Check the three things this deployment promises

**It reads a live letter end to end.** Open the console, choose a language, photograph a synthetic
letter from `src/plainletter/samples/` printed on paper, and watch the stages arrive. The same
reading through `agentcore invoke` with `"stream": true` shows the raw event stream.

**Consent decides what is kept.** Read a letter with the consent box unticked: the answer carries
`"case": null` and nothing is written. Tick it: the answer carries a case id, the desk card prints
it, and `agentcore status` shows the memory store holding one event under that id. Bring the id
back on a second reading and the console opens with the earlier reading on its first line. Events
expire after thirty days, as the privacy page says.

**No letter reaches a trace or a log.** Open CloudWatch, Application Signals, Transaction Search,
and find the trace of a reading. The Strands spans (`invoke_agent`, `chat`, `execute_tool`) show
`[REDACTED]` where a prompt, an answer or a tool argument would be: the agent pins that policy in
code (`src/plainletter/telemetry.py`) and the deployment repeats it in `agentcore.json`. The span
named `plainletter.reading` carries counts and outcomes only: how many facts were grounded, whether
a person had to take over, which tools ran and how each ended. The runtime log in CloudWatch holds
durations and failure types. Search both for any amount, date or name from the letter you read:
there is none.

## Costs and cleanup

The runtime bills per second of CPU and memory while a reading runs and for the idle window after
it (five minutes, set in `agentcore.json`). The memory store bills per event. A hackathon's worth of
readings costs a few euros. To remove everything the deploy created:

```sh
agentcore remove all
agentcore deploy
```
