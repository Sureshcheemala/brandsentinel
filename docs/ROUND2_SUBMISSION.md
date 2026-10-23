# BrandSentinel: Round 2 submission (The Build)

Team HACKVECA · TechCircuit · Round 2, 22 to 25 October 2026

**Links** (fill in before submitting; each must open without signing in)

- Working project: `[deployed URL]` (demo accounts are one click on the login page)
- Source code: `[public repository URL]`

## 1. Build-window disclosure (read first)
The first version of this application was generated with an AI assistant (Claude, by Anthropic) on **21 October 2026 (IST), before the Round 2 window opened on 22 October at 10:00 AM IST**. That base includes the rules engine, API and workflow server, web UI, brand kit, tests and evaluation sets. It is disclosed here as previously created code, as the event rules require.

Work done **inside the window** (from 23 October) is recorded in the repository's commit history with true timestamps and listed in section 6. Judges should score the in-window work and the product as it stands. Nothing in this repository has been backdated.

## 2. What BrandSentinel is
A pre-publication brand-governance tool. A creator submits text, Markdown, HTML, a Word document or an image. The system checks it against the organisation's approved guidelines, facts, terminology and assets, explains each finding with the rule or fact behind it, and suggests a minimal fix that keeps the author's intent. People decide: nothing is applied automatically, and reviewers and managers control approval. Sample brand: Lumora (fictional).

## 3. Completed features
| Area | Feature |
|---|---|
| Review formats | Plain text, Markdown, HTML, .docx (text and image alt text), PNG/JPG/SVG images |
| Terminology | Brand and product names, preferred words, inclusive language |
| Tone and language | Hype words, jargon, ALL-CAPS, repeated exclamation marks, long sentences |
| Facts and claims | Numbers matched to approved facts: supported, contradicts, expired, unverified; unsupported superlatives and guarantees; missing "Terms apply" line |
| Accessibility | Missing or meaningless alt text, vague link text, WCAG contrast (4.5:1, 3:1 large) with a palette-based fix |
| Visual | Off-palette colours, unapproved logo files, distorted logo proportions, small images |
| Explainability | Every finding shows quoted evidence, a reason, and the guideline or approved fact (ID, title, excerpt); a claims-checked panel |
| Suggestions | Opt-in only; stale suggestions are refused instead of corrupting text |
| Workflow | Roles (creator, reviewer, manager, admin), comments, revision history with diffs, request changes, approve, publish, audit log, downloadable review report |
| Human control | High-severity findings block approval; manager override needs a reason and is logged; authors cannot review their own work or dismiss high-severity findings |
| Insights | Repeated mistakes by rule and team, accepted vs dismissed counts, possibly-unclear-guideline signal, average revisions to approval |
| Governance | Versioned brand kit editable by admin with validation, AI and data disclosure page |
| Security | Hashed passwords, login throttling, strict Content-Security-Policy, path-traversal protection, input validation |
| Usability | One-click demo accounts, sample drafts, keyboard focus styles, labelled controls, works at phone width |

## 4. Technology and implementation
- **Back end:** Python 3.13 standard library only (`http.server`, `sqlite3`, `hashlib`, `zipfile`, `difflib`, `re`). Rules engine in `app/engine.py`, API and workflow in `app/server.py`, storage in `app/db.py`.
- **Front end:** hand-written HTML, CSS and JavaScript, no framework, no CDN. User content is rendered with `textContent`, never `innerHTML`.
- **Data:** SQLite; the brand kit is a versioned JSON file (`data/brandkit.json`) of guidelines, approved facts with expiry dates, terms, palette and assets.
- **AI:** a source-grounded review using Claude (Anthropic API, model `claude-sonnet-5-5`, changeable with `BS_AI_MODEL`), **off by default** and enabled by `BS_EXTERNAL_AI=on` plus an `ANTHROPIC_API_KEY` secret on the host. It retrieves only the guideline and approved-fact snippets relevant to the draft and sends those plus the draft. Every AI finding must cite a snippet that was sent and quote the draft verbatim, or it is discarded. AI findings are labelled, low-confidence, need human judgement, offer guidance only (never an automatic replacement) and are never applied automatically. Any API failure falls back to the rules result. **Tested with a fake model (14 tests); not yet run against the live API**, so enable it on the deployed site and check one real review before relying on it.
- **Deployment:** `Dockerfile` (listens on `PORT`); health check at `/api/health`.
- **Decision rationale:** deterministic rules are explainable, free of hallucination and need no confidential data to leave the organisation; a model is meant to be added only as a labelled, source-grounded second opinion.

## 5. Changes from the Round 1 plan
| Round 1 plan | What was built | Why |
|---|---|---|
| React + TypeScript front end | Vanilla JavaScript single-page app | No build step; runs anywhere; easier for judges to open |
| FastAPI + PostgreSQL + pgvector | Standard-library Python server + SQLite | Zero dependencies; no database server to host; retrieval is not needed while checks are rule-based |
| Language model for tone, claims and rewrites | Rules engine as the core, plus an optional source-grounded Claude review for tone and guideline issues | Reliability and explainability first; the model is a labelled second opinion. Claim extraction and rewrites by model are Round 3 |
| PDF input | Not built | Deferred to Round 3 |
| Encryption at rest, SSO, Docs/Word add-ins | Not built | Deferred to the roadmap |
| Round 1 "three improvements" (accuracy, image checks, clarity report) | Largely delivered in basic form | Replaced by the new Round 3 improvements below |

## 6. Work completed inside the window
Starting 23 October (see the repository's dated commits):
- One-click demo accounts on the login page, so judges can use the product without guidance (checked in a real browser).
- `/api/health` endpoint and test.
- Source-grounded AI review (`app/llm.py`): retrieval of relevant guideline and fact snippets, mandatory source citation and verbatim quotes, discard of anything unsupported, failure fallback, prompt-injection hygiene, AI labelling in the UI and disclosure page, and 14 new tests (62 pass in total).
- This Round 2 submission, the disclosure statement and the PDF.
- Public repository with dated commits. The first commit is the disclosed 21 October base; later commits are in-window work.

Done on 21 October, so it belongs to the disclosed base and is **not** claimed as in-window: the scripted Chromium test of the full workflow, the phone-width scrolling fix, and the Round 3 presentation draft.

## 7. Evidence of testing
62 automated tests pass (14 cover the AI module using a fake model). Rules engine: 36 of 36 expected findings with 0 false alarms on the 45-case development set; 7 of 7 with 0 false alarms on 12 held-out cases. The cases were written by the developers for their own rules, so these figures show the engine does what its rules say, not accuracy on real marketing copy. **No real-user testing has been completed yet.** Details and screenshots: `docs/TESTING.md`, `docs/screenshots/`.

## 8. Three improvements for Round 3
1. **Measured AI quality: model-assisted claim extraction and rewrites, evaluated.** Extend the AI review from tone to claim extraction against approved facts and to suggested rewrites, build a labelled evaluation set run against the live model, and report precision, recall, false alarms and the share of AI findings that reviewers accept, rules-only vs rules-plus-AI. Add admin controls (per-workspace on/off, redaction of confidential names before sending, spend limit).
2. **PDF input and real visual analysis.** Extract text and images from PDFs (including per-page findings), detect logo presence and clear-space, measure on-palette colour share and text-over-image contrast from pixels, and flag layout issues on image and PDF assets.
3. **Integrations and team workflow.** Reviewer assignment and due dates, email or Slack notifications on submit, changes requested and approval, a publish webhook for a CMS, and a minimal Google Docs or Word add-in that sends a draft for review. Includes SSO-ready authentication.

Each is a new capability, not a cosmetic change, and each is tested and evaluated in Round 3.

## 9. Known limitations
Rule-based claim matching needs testing on real copy; no real-user or screen-reader testing yet; AI review not yet run against the live API; English only; SQLite and a single server suit a demo, not heavy traffic; no encryption at rest. See `docs/LIMITATIONS_ROADMAP.md`.

## 10. Team contributions
To be completed by each member accurately: `docs/CONTRIBUTIONS.md`. Do not claim work you did not do; judges may ask any member to explain or demonstrate their part.
