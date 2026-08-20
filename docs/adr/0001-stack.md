# ADR 0001: Stack

Date: 2026-08-20
Status: accepted

## Context

Plainletter reads photographed or PDF official letters, extracts and verifies facts, explains them
in the reader's language, plans next steps and prints a desk card for help-desk volunteers. It is
built solo in about three weeks. The agent framework is fixed by the event (Strands Agents SDK,
Python), the model provider is Amazon Bedrock, and the deployment target is Amazon Bedrock
AgentCore. Everything else was chosen for the smallest number of moving parts that still clears the
quality bar: a complete product, not a proof of concept, with a real web console, a printable
artefact, right-to-left languages and a live demo link.

## Decision

Agent (Python)

- Python 3.11 managed by uv, one package in a `src/` layout at the repo root (`src/plainletter`),
  one lockfile (`uv.lock`). A uv workspace with separate agent and tools packages was considered and
  rejected: it adds packaging surface a single-agent repo does not need.
- `strands-agents` 1.52, `strands-agents-tools` 0.8, `bedrock-agentcore` 1.22, `pydantic` 2.13.
  Structured output through Pydantic models; orchestration with `GraphBuilder`; guardrails with
  `strands.interventions` and hooks; `icalendar` for the reminder file.
- Models: Amazon Bedrock EU geo inference profiles invoked from eu-central-1, so requests stay in
  EU regions: `eu.anthropic.claude-sonnet-4-6` for reading, explaining and drafting,
  `eu.anthropic.claude-haiku-4-5-20251001-v1:0` for classification and cheap checks. Both accept
  image input. Model IDs are configuration, not code.
- Intake: images (PNG, JPEG, WebP) go to the model as Bedrock image content blocks; PDFs go as
  Bedrock document blocks first, with pypdfium2 rasterisation as the fallback for scanned or
  low-quality PDFs (pypdfium2 ships wheels and needs no system binary, unlike pdf2image and Poppler).
- Local server: `BedrockAgentCoreApp.run()`, the same ASGI application AgentCore Runtime invokes in
  production. No separate FastAPI wrapper: it would duplicate the entrypoint contract and drift.
- Tests: pytest with a fake Strands `Model` fixture for deterministic agent tests; real Bedrock
  calls only in an explicitly marked integration tier. Hypothesis for the deadline and money math.

Console and landing page (TypeScript)

- Next.js 16 (App Router) with React 19 and Tailwind CSS 4 in `web/`. Tailwind 4's logical
  properties make right-to-left layouts a `dir="rtl"` flip with no plugin. The landing page and the
  privacy page are static routes inside the same app; the desk card is a print stylesheet.
- The browser never talks to AWS. A Node route handler in the Next.js app signs requests to the
  AgentCore Runtime endpoint with the official `@aws-sdk/client-bedrock-agentcore` client (SigV4,
  the Runtime default); credentials live on the server host only. JWT and OAuth through AgentCore
  Identity are a follow-up for real per-volunteer accounts, which v1 does not have.
- Hosting: Vercel (Hobby), Node serverless runtime for the proxy route.

Deployment and operations

- AgentCore Runtime, Memory (consent-gated) and Observability in eu-central-1, set up with the
  AgentCore CLI in a dedicated phase. Strands emits OpenTelemetry traces that AgentCore
  Observability collects.

Quality floors

- Python: ruff (lint and format), mypy strict, bandit, pip-audit, pytest.
- Repository: jscpd duplication scan, `check-ship-artifacts` (no process artefacts tracked),
  `check-client-secrets` (no secrets in a client bundle), `verify:ship` as the single ship command,
  the same gate chain in the pre-commit hook and in CI. The JavaScript gates (ESLint complexity and
  cognitive complexity, compat, dependency-cruiser, size-limit, schema-dts) are added when `web/`
  lands.

## Alternatives considered

| Alternative | Why not |
|---|---|
| SvelteKit 2 | The lightest runtime and the easiest Lighthouse numbers, but less prior art for streaming agent output and signed AWS proxies; a legitimate second choice, not a wrong one |
| Astro | Content-first islands model fights an interactive console with upload, streaming and an editable draft |
| pdf2image | Needs Poppler inside the runtime image for no capability pypdfium2 lacks |
| A FastAPI server around the agent | Duplicates what `BedrockAgentCoreApp` already serves and risks diverging from the production entrypoint |
| AgentCore Identity (JWT/OAuth) in v1 | Identity infrastructure for a product with no user accounts |
| A separate static site for the landing page | Two deployables and two design setups for a few static pages |

## Consequences

- Two toolchains in one repo (Python and Node). CI installs both; `package.json` at the root
  carries the gate scripts and, once `web/` exists, the workspace entry for the console.
- The Vercel host holds AWS credentials for the proxy route. They are environment variables on
  the host, never in the client bundle; the client-secret gate runs on every build.
- Lighthouse discipline matters on the console route (keep the landing and print routes static).
- The Python version is pinned to 3.11 through `.python-version` until the AgentCore Runtime base
  image and the dependency set are re-checked against 3.13.
