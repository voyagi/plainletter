# Privacy accountability

Written 2026-08-25 for Plainletter. This is the working record behind the privacy page: what is
processed, why it is lawful, what could go wrong for the person the letter belongs to, and what the
product does about it. The privacy page at `/privacy` is the short version written for a visitor;
this file is the version an operator, a library, or a supervisory authority would ask for.

One thing in here is not settled and is marked **OPEN**. It needs the operator, not the code.

## What this product is, in data protection terms

A person hands over an official letter addressed to them. Plainletter reads it, checks every date
and amount against the letter itself, explains it in two languages, works out the deadline, lays out
the next steps, and prints a one page card. The letter is the input; almost nothing survives the
request.

- **Controller.** Whoever runs the deployment, which is why the privacy page takes the name and the
  contact address from that deployment's own environment (`PLAINLETTER_CONTROLLER_NAME` and
  `PLAINLETTER_CONTROLLER_CONTACT`) rather than from the source. Unset, the page says the
  organisation running the desk is the controller and tells the visitor to ask at the counter, which
  is true of every installation. For the hosted demo the two are set to Taranity and
  hello@taranity.com. A library running its own copy is the controller of that copy and sets its own.
- **Data protection officer (Article 37).** Not required for the hosted demo, and that is a
  determination rather than an assumption about size. 37(1)(a) does not apply: Taranity is not a
  public authority or body. 37(1)(b) does not apply: the core activity is reading one document a
  person hands over at their own request, which is neither regular nor systematic monitoring of data
  subjects, and nothing here observes anybody over time. 37(1)(c) does not apply: no Article 9
  special category or Article 10 criminal-offence data is processed as a core activity, and a
  letter's own content is incidental to a single request rather than a category the service is built
  on. **This determination belongs to the deployment, not to the code.** A municipality or another
  public body running its own copy is caught by 37(1)(a) and has to name its DPO on the page, which
  is one more reason the controller block is deployment-configured. Article 13(1)(b) applies only
  where a DPO exists, so an unset deployment satisfies 13(1) with 13(1)(a) alone.
- **Processors.** Amazon Web Services, for model inference (Amazon Bedrock) and for the runtime and
  the optional case store (Amazon Bedrock AgentCore). The console's host, if the console is hosted.
- **Data subjects.** The person the letter was sent to, and anybody else named in it. The second
  group matters: a letter from a bailiff can name a partner, an employer or a landlord who never
  walked into the library.
- **Categories of data.** Name, address, national identity number (BSN), bank account number,
  amounts owed, reference numbers, deadlines, and whatever else the letter carries. Depending on the
  sender, the fact of processing can reveal debt, benefits, immigration status or health insurance
  arrears. None of that is special category data under Article 9 by itself, and all of it is
  sensitive in the ordinary sense of the word.

## Processing register

| Activity | Personal data | Purpose | Legal basis | Retention |
| --- | --- | --- | --- | --- |
| Reading one letter | The uploaded image or text and everything in it | Explain the letter to the person it was sent to, at their request | Art. 6(1)(b) or 6(1)(a): the person asked for this specific service in this specific moment | For the length of one request. Held in memory, never written to disk |
| Model inference | The same content, sent to Amazon Bedrock in the EU | Produce the transcription, the reading, the explanation, the plan and the draft | Same basis, same request | Not retained by the product, and not retained by Bedrock either for the model this product uses. See the sub-processor table for the exact position and the two carve-outs |
| Keeping a case | Derived, masked display values only: sender, letter type, reference, dates, amounts, steps, whether a person had to take over | Let a returning visitor continue where they stopped | Art. 6(1)(a) consent, asked out loud at the desk, recorded per request | 30 days, then deleted by the store itself. Erasable on request at any time |
| Tracing | Counts and outcomes only: how many facts were grounded, how many issues, whether a person is needed, the sender id when the knowledge base knows it | Know whether the service is working without reading anyone's letter | Art. 6(1)(f), the operator's interest in a working service, with no letter content in scope | The trace backend's own retention, set by the operator |
| Metering the console | A network address, and a random marker in a session cookie | Keep an unauthenticated, metered endpoint standing | Art. 6(1)(f), security and abuse prevention. The cookie is strictly necessary under the ePrivacy rules, so it is set without a consent banner | In memory, for the life of the serving process |

Nothing here profiles anybody, makes an automated decision with legal effect under Article 22, or
sells, shares or publishes anything. Plainletter explains a letter and says when a professional must
take over; it does not decide anything about the person.

## Data protection impact assessment (Article 35)

An assessment is required, and it is required by more than one limb of Article 35(3): the product
processes data revealing debt, benefits and immigration status about people in a vulnerable position
relative to the controller, at scale if the 861 Dutch help desks are the audience, using a
technology whose failure mode is a confident wrong answer.

### 1. The processing, described (Art. 35(7)(a))

One letter, one request. The pages are decoded in memory, re-encoded (which drops the photograph's
EXIF block, and with it where it was taken), and sent to a vision model on an EU inference profile
sourced from Frankfurt. A photographed letter is transcribed by one turn and read by a separate one.
A deterministic verifier then checks every date, amount and reference against the letter's own words.
Explaining, planning and drafting happen after that check and are bounded by it. The answer is
masked on the way out, printed on a card, and forgotten. With consent, and only then, a short record
of derived values is filed under a printed case number for 30 days.

### 2. Necessity and proportionality (Art. 35(7)(b))

The purpose cannot be met without the letter: the whole service is reading the specific document in
front of the person. What is proportionate is what the product does with it afterwards, and the
design is built around keeping that as close to nothing as it can be.

- No account, no login, no profile, no identifier that follows anybody between visits except a case
  number the visitor holds on paper and can throw away.
- The image and the text exist for one request and are never written to disk or to a log.
- The identity number and the bank account are masked before anything is shown, printed, traced or
  remembered.
- What a consented case keeps is derived and masked: no name, no address, no passage from the
  letter, no explanation. A visitor who agreed to "remember my case" did not agree to a copy of a
  government letter with their identity number on it, and the record is built so it cannot hold one.
- Processing stays in the EU: `eu-central-1` as the source region, EU-only cross-region inference.

### 3. Risks to the people the letters belong to (Art. 35(7)(c))

| Risk | How it would happen | Severity |
| --- | --- | --- |
| A wrong deadline or amount is acted on | The model states a plausible value the letter does not carry | High. A missed objection window cannot be reopened |
| A fraudulent route is followed | A letter carries an instruction aimed at the agent, naming a phone number or account to pay | High. This is the injection case, and it is the one that costs money directly |
| The letter's content leaks into a log or a trace | Prompt and completion content is emitted by default by most agent tracing | High. Whole letters, including identity numbers, in an operator's log store |
| The stored case is more than the visitor agreed to | A record that copies the letter rather than the derived values | Medium to high |
| A case number is guessed | Eight readable characters, no other key | Medium. The record holds no name, but it is somebody's letter history |
| The endpoint is abused | An unauthenticated, metered path on the public internet | Medium for the operator's bill, and it degrades the service for real desks |
| A third party in the letter is processed without knowing | A bailiff's letter names other people | Medium, and unavoidable in kind: the letter is what it is |

### 4. Measures (Art. 35(7)(d))

| Risk | Measure | Where it lives |
| --- | --- | --- |
| Wrong deadline or amount | A deterministic verifier that grounds every value in the letter's own words, an intervention on the model's answer boundary that refuses an ungrounded value before it exists, and a final pass that refuses the whole reading if a stray value survived | `src/plainletter/verify.py`, `guard.py`, `pipeline.py` |
| Fraudulent route | Routes come from a curated knowledge base through a tool call, and a step naming anything the knowledge base did not hand out is refused whole. Every prompt says the letter is data and never an order | `src/plainletter/tools.py`, `pipeline.py`, `reading_model.py`, `tests/test_injection.py` |
| Letter content in logs or traces | The SDK's trace redaction policy is pinned before the first agent is built, so prompts, answers and tool arguments never reach a span. Agents run with no console handler. Failures are logged by exception type, never by message | `src/plainletter/telemetry.py`, `tests/test_traces.py` |
| Case holds too much | The record is a fixed set of derived, masked display fields, and a test asserts that no name, address or passage survives into it | `src/plainletter/memory.py`, `tests/test_retention.py` |
| Guessed case number | The alphabet excludes look-alike characters and the endpoint that reads a case is rate limited and quota'd per address and per browser | `src/plainletter/memory.py`, `web/src/server/limits.ts` |
| Abuse of the endpoint | An origin check, a size cap, a burst limit, a daily quota in the console, a second daily ceiling in the agent claimed before the first model call, and a token ceiling on every model call | `web/src/app/api/read/route.ts`, `src/plainletter/spend.py` |
| Third parties in the letter | The same masking and the same non-retention apply to every person named. Nothing about them is stored, and the identity number and account mask does not care whose it is | `src/plainletter/redact.py` |

### 5. Residual risk

The model can still be wrong about something the verifier does not check, which is prose: a
consequence stated too softly, an explanation that misses a nuance. The product answers this by
saying, on the card itself, that it is not legal advice, and by routing a letter to a named human
service whenever the reading did not fully check out or the sender's procedure was never confirmed
against an official page. Nine of the twelve senders in the knowledge base are marked unverified on
purpose, and those letters always go to a person.

Residual risk is assessed as acceptable for a help desk where a volunteer is present, and the
product is not designed to be used with no human anywhere in the loop.

### 6. Review

This assessment is reviewed when the processing changes in kind: a second country, a stored letter,
an account system, a long-term memory strategy, or any automated decision. Consulting the Autoriteit
Persoonsgegevens under Article 36 is not required while the measures above hold the residual risk
low.

## Rights, and how each one is answered

There is no account and no name in any store, so most rights are answered by there being nothing to
answer with. What exists is a case, keyed by the number printed on the card.

| Right | How it is met |
| --- | --- |
| Access (Art. 15) | The desk recalls a case by its number and shows every reading under it. That is the whole record |
| Rectification (Art. 16) | A record is derived from one reading. A wrong reading is re-read and the old case erased |
| Erasure (Art. 17) | Built in: a request carrying `forget` and the case number deletes every reading under it, immediately, without reading anything. Everything expires by itself after 30 days regardless |
| Restriction (Art. 18) | Erasure is the operative one here, and it is immediate. There is no processing to restrict once a request has ended |
| Portability (Art. 20) | The reading is handed over as a printed card and a calendar reminder at the desk, and a case is returned as structured JSON |
| Objection (Art. 21) | Nothing is kept without consent, and the consent is withdrawn by erasing the case |
| Complaint | To the Autoriteit Persoonsgegevens, autoriteitpersoonsgegevens.nl, or to the supervisory authority of the country the deployment serves |

## Sub-processors

| Party | What reaches them | Where | What the operator must confirm |
| --- | --- | --- | --- |
| Amazon Web Services, Amazon Bedrock | The letter's image or text, and the prompts and answers of one reading | `eu-central-1`, with EU-only cross-region inference profiles | Accept the AWS GDPR data processing addendum on the account, and confirm the model provider's terms on Bedrock |
| Amazon Web Services, AgentCore Runtime and Memory | The request payload, and the consented case record | Same region | Same addendum. Confirm the memory store's expiry is 30 days after deployment |
| The console's host | The upload as it passes through the proxy, plus network addresses in its own access logs | The operator's choice, EU region recommended | A processor agreement and the log retention the host applies |

Two things about Bedrock are worth stating exactly, because a DPIA that hand-waves them is worth
nothing. Both were read on the AWS documentation on 2026-08-25.

- Bedrock runs a zero operator access and zero data retention model, so by default it does not store
  model inputs or outputs, and model providers have no access to prompts or completions at all. The
  documented retention carve-outs name specific models, and the model this product uses is not among
  them. **Changing the model id can therefore change the retention position**, which is one more
  reason the configured id is probed at startup and written down in the code.
- Bedrock screens image inputs for child sexual abuse material and may store and review a flagged
  input to decide whether it is. This product uploads photographs, so that check applies to it. It
  is not optional and it is not a reason to avoid the service; it is a fact that belongs in this
  file rather than in a surprise.

AWS is a group with a United States parent, which is the usual transfer question. The position taken
here: processing and storage are pinned to EU regions and EU-only inference routing, and the operator
relies on the AWS data processing addendum and its transfer terms for anything else, such as support
access. An operator with a stricter requirement should say so in their own privacy page rather than
inherit this one.

## EU AI Act Article 50 determination

Recorded 2026-08-25. The transparency obligations in Article 50 have applied since 2026-08-02, and
the four-month marking transition does not reach a product placed on the market after that date, so
this product is inside them from its first public day.

**50(1), a system that interacts with a natural person: APPLIES.** A visitor can use this at home
alone, and even at the desk the answers are written to the person rather than to the volunteer. The
exemption for what is obvious to a reasonably well-informed person is not one to lean on here: the
audience is specifically people who are not well informed about the systems in front of them. The
disclosure is shipped where the interaction starts, on the intake screen before the first letter
goes in, and it is written in the volunteer's own language rather than in a footer.

**50(2), machine-readable marking of generated text: APPLIES.** The explanation, the action plan
and the draft letter are all generated text, and the draft in particular leaves the building as a
document somebody signs. Human oversight does not carry the editorial-responsibility exemption here
either: the visitor may be alone. Shipped as three things, because a text file has no one obvious
place to put a mark:

- The printed desk card carries `<meta name="generator">` naming the AI system and
  `<meta name="ai-generated" content="true">`, plus a sentence a person can read.
- The calendar reminder carries it in `PRODID`, which is the field every calendar application
  reads, and again in the description a person sees.
- The console says it on the intake screen, before anything is uploaded.

**50(3), emotion recognition and biometric categorisation: does not apply.** Neither is present.

**50(4), deepfakes and text published on matters of public interest: does not apply.** Nothing this
product writes is published anywhere. It goes to the person whose letter it is.

A change that would reopen this determination: publishing readings, adding a conversational mode,
or removing the volunteer from the picture entirely.

## Breach procedure

1. Take the console offline or set the daily ceiling to zero, which closes the reading service
   without taking the deployment down.
2. Rotate the console's AWS access key and any deploy credentials.
3. Preserve CloudWatch traces and the console's host logs. They hold counts and outcomes rather than
   letters, which is the point, and they are still the evidence.
4. Establish what was affected. The product stores no letters, so the realistic exposures are the
   consented case records and the network addresses in a host's access logs.
5. If a personal data breach is likely to have occurred, assess Articles 33 and 34 within 72 hours,
   and notify the Autoriteit Persoonsgegevens if the threshold is met.
6. Record the timeline, what was affected, what was done, and whether anybody was notified.

## Human launch gate

- Controller: set per deployment through the environment, and set to Taranity, hello@taranity.com
  for the hosted demo. A registered legal form, address and company number belong there too once
  the studio has them; a trading name and a working contact address are what Article 13(1)(a) asks
  for. **Any other operator must set their own before serving anybody**, and an unset deployment
  says so on the page rather than naming somebody else.
- **OPEN.** Accepting the AWS data processing addendum on the account the runtime lives in, and
  confirming the model provider terms in the Bedrock console.
- A legal read of the privacy page before it serves real letters. Everything in it is a description
  of what the code does, and none of it is legal advice about the operator's own position.
- If the console is hosted somewhere with its own logs, that host's retention goes in the table
  above with a real number.
