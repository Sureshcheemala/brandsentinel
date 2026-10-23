# Architecture and technical decisions

```
Browser (single-page UI, vanilla JS, no framework, strict CSP)
   │  JSON over HTTP, bearer-token sessions
   ▼
app/server.py  ── routing, auth, roles, workflow state machine, insights, audit
   │                │
   │                ├── app/engine.py   deterministic checks, each finding cites its source
   │                ├── app/llm.py      OPTIONAL tone second opinion (off by default)
   ▼                ▼
app/db.py ── SQLite: users, sessions, brandkit (versioned), items, revisions, comments, events, audit
data/brandkit.json  guidelines · terminology · approved facts (with expiry) · palette · assets
```

## Review pipeline (per revision)
text → (for HTML, tags blanked so offsets align) → terminology → voice → claims (sentence split that keeps `99.5%` whole; match to approved facts by keywords; compare numbers; check expiry) → accessibility and visual checks → de-duplicate → sort by position and severity → store with the brand-kit version used.

Every finding stores: rule id, category, severity, character span, quoted evidence, reason, source (guideline or fact id, title, excerpt), suggestion (`replace`, `replace_hex`, `append`, or `manual`), confidence, `needs_human`, `ai_assisted`, and a stable `key` (rule + hash of the quote) used to remember dismissals across revisions.

## Workflow
`draft → in_review → (changes_requested → draft) | approved → published`

| Action | Who |
|---|---|
| Create, edit, accept suggestion, submit | owner, only in draft or changes_requested |
| Dismiss low/medium finding (reason required) | owner or reviewer+ |
| Dismiss high-severity finding | reviewer, manager or admin who is not the author, only in review |
| Approve / request changes (comment required) | reviewer, manager, admin; never the author |
| Approve with open high findings | manager or admin, with a recorded override reason |
| Publish | manager or admin |
| Edit brand kit | admin (new version; regexes validated) |

## Main technical decisions
1. **Rules first, AI second.** Terminology, numbers, contrast and file checks have exact answers, so a deterministic engine gives reproducible, explainable results with no data leaving the server. A language model is only a labelled optional extra for tone.
2. **Grounding is mandatory.** A finding without a source is not produced. Claims that match no approved fact are "unverified" and routed to a human rather than called false.
3. **Suggestions are data, not actions.** Applying one creates a new revision only when the owner clicks Accept, and it is refused if the text moved since the finding. Judgement-heavy suggestions are `manual` and cannot be auto-applied.
4. **Standard library only.** No install step and no supply-chain risk for the demo; SQLite keeps the build portable. Trade-off: a production version would move to a framework, Postgres and a proper auth provider (see roadmap).
5. **Stable dismissal keys.** Dismissals survive edits that shift offsets, so creators are not nagged by findings a reviewer already ruled on.
6. **Insights come from decisions.** Accepted vs dismissed counts per rule reveal guidelines that are unclear or too strict, which is the "where are the guidelines unclear" requirement.
7. **UI renders with textContent only** and the server sets a strict Content-Security-Policy, so user content cannot execute as script.

## Data model highlights
`revisions` keep the full text, findings, claims, brand-kit version and author for every change, which gives revision history, diffs and reproducibility. `events` records accepted, dismissed and override decisions. `audit` records logins, submissions, decisions, overrides, publishes and brand-kit edits.
