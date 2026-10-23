# Disclosures (submission integrity)

## AI assistance
The source code, tests, evaluation cases, sample brand kit and documentation in this repository were drafted with an AI assistant (Claude, by Anthropic) in a conversation with a team member, then run and tested. Team members must be able to explain every part during judging. **Team to complete:** who reviewed which files, and what was changed by hand.

## Libraries, templates and external services
- Runtime: Python standard library only (http.server, sqlite3, hashlib, zipfile, difflib, re, json). No third-party packages, templates or boilerplate.
- Front end: hand-written HTML, CSS and JavaScript. No framework, CDN or font downloads.
- External services: none used by default. Optional Anthropic API call in `app/llm.py` (off unless `BS_EXTERNAL_AI=on` and `ANTHROPIC_API_KEY` are set).
- Data: the "Lumora" brand kit and all test snippets are fictional and written for this project. No datasets were downloaded.
- Statistics quoted in the Round 1 plan come from public web sources listed there; several are vendor-published and second-hand.

## Build-window statement
The base application (rules engine, server, UI, brand kit, tests, evaluation sets and documentation) was generated with Claude on **21 October 2026 (IST)**, before the Round 2 window opened on 22 October at 10:00 AM IST. It is disclosed as previously created code. Work done inside the window starts on 23 October and is listed in `docs/ROUND2_SUBMISSION.md` section 6, with true timestamps in the repository's commit history. Round 1 research and planning were done before the window, as the rules allow.

**Team to confirm:** that this statement is accurate and that each member can explain the code.
