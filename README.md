# BrandSentinel

Pre-publication brand governance. A creator submits text, HTML, Markdown, a Word document or an image. BrandSentinel checks it against the organisation's approved guidelines, facts, terminology and assets, explains every finding with the rule or fact behind it, and suggests a fix that keeps the creator's intent. Humans decide: suggestions are never applied automatically, and reviewers, managers and admins control approval.

Built for the Inkloom AI brand-governance challenge. Sample brand: **Lumora** (a fictional company).

## Run it (no installation, standard library only)

```bash
python3 run.py                  # http://127.0.0.1:8000
python3 seed_demo.py            # optional: fills the Insights page with demo activity (in a second terminal)
python3 -m unittest discover -s tests -t .      # 62 tests
python3 evaluation/eval.py                      # precision/recall on 45 labelled cases
python3 evaluation/eval.py heldout.json         # 12 cases not used for tuning
```

Requires Python 3.9+ (developed on 3.13). Deployment and the optional AI setting: see `docs/DEPLOY.md`. Docker: `docker build -t brandsentinel . && docker run -p 8000:8000 brandsentinel`.

Demo users (password `demo123`, change with `BS_DEMO_PASSWORD`): `ana`, `ben` (creators), `mira` (reviewer), `raj` (manager), `root` (admin).

## Two-minute demo
1. Log in as `ana` → **New review** → load sample *Launch email (many issues)* → **Create and review**.
2. Click a highlighted phrase to jump to its finding. Each finding shows the quoted evidence, the reason, and the guideline or approved fact it relies on.
3. **Accept suggestion** on the wrong "guys" wording (creates revision 2; see the diff). Try a claim finding: its suggestion is manual because a person must decide.
4. Try to dismiss a high-severity finding as `ana`: refused. Submit for review.
5. Log in as `mira` → open the item → **Request changes** with a comment. Back as `ana`, fix, resubmit; `mira` approves; `raj` publishes.
6. `raj` → **Insights** for repeated mistakes and rules that look unclear; **Audit log** for every decision; **AI & data** for disclosure.

## What it checks
| Area | Checks |
|---|---|
| Terminology | brand and product names, preferred words, inclusive language |
| Tone | hype words, jargon, shouting (caps, repeated "!"), sentence length |
| Facts and claims | numbers matched to approved facts (supported, contradicts, expired, unverified), unsupported superlatives and guarantees, missing offer terms line |
| Accessibility | image alt text (missing or meaningless), vague link text, WCAG contrast ratio (4.5:1, 3:1 large) with a palette-based fix |
| Visual | off-palette colours (nearest approved colour suggested), unapproved logo files, distorted logo proportions, small images |
| Formats | plain text, Markdown, HTML, .docx (text and image alt text), PNG/JPG/SVG images |

## Folder map
`app/engine.py` rules engine · `app/server.py` API and workflow · `app/db.py` storage · `app/llm.py` optional AI (off) · `app/static/` UI · `data/brandkit.json` sample brand kit · `tests/` · `evaluation/` · `docs/` documentation.

See `docs/SUBMISSION_CHECKLIST.md` for how each file maps to the Round 1, 2 and 3 requirements and what still needs to be done by the team (deployment link, demo video, user testing, contribution statements).
