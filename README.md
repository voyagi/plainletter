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

## Status

Under construction. Setup instructions, the architecture diagram and the demo land here as the
build progresses.

## Repository layout

| Path | What lives there |
|---|---|
| `src/plainletter/` | The agent: reading, classification, verification, explanation, planning, rendering |
| `samples/` | Synthetic sample letters used for the demo and the tests (no real people, no real data) |
| `web/` | The desk console and the public landing page |
| `tests/` | Test suite |
| `scripts/` | Repository gates run in the pre-commit hook and in CI |
| `docs/` | Architecture, decisions, privacy notes |

## License

Apache-2.0. See [LICENSE](LICENSE).
