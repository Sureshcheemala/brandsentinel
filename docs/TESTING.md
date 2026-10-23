# Testing, reliability and changes during development

Results below were produced by running the commands in this repository on the build machine (Python 3.13).

## Automated tests: 62 passing (47 from the 21 Oct base, 15 added 23 Oct)
`python3 -m unittest discover -s tests -t .`
- `tests/test_engine.py` (28): terminology (including domains and emails not flagged), claims (supported, contradicted, expired, unverified, offers), tone, contrast maths and fix round-trip, images and links in HTML and Markdown, decorative empty alt allowed, docx extraction, PNG size and logo distortion, suggestion apply/refuse, every finding has a source.
- `tests/test_api.py` (19): login, throttle, security headers, path traversal, validation, accept/dismiss rules, dismissal persistence across revisions, role restrictions, privacy between creators, the full workflow (submit, request changes, resubmit, approve, publish), override rules and audit, comments, docx and image flows, insights access, brand-kit admin and regex validation, AI disclosure default.

## AI review tests (added 23 Oct, `tests/test_llm.py`, 14 tests, fake model)
The Claude call is replaced by a fake transport so the safety logic is proven without a network: off by default and nothing sent when off; needs both the switch and a key; a valid, cited, verbatim finding is kept and labelled AI-assisted with manual-only guidance; findings citing an unknown or unsent source, or quoting text not in the draft, are discarded; duplicates of rules findings are dropped; a cap of 5; timeouts, bad JSON and malformed replies return no findings; a prompt-injection draft cannot produce a finding that fails the checks; only relevant snippets plus the draft are sent; and an end-to-end API test shows AI findings flowing into a review and the disclosure page. **The live Anthropic API has not been exercised**: enable it on the deployed site and review one draft to confirm.

## Accuracy evaluation of the rules engine
`python3 evaluation/eval.py` (45 labelled snippets, used while developing) and `python3 evaluation/eval.py heldout.json` (12 snippets written afterwards, not used for tuning).

| Set | Cases | True positives | False positives | Missed | Precision | Recall |
|---|---|---|---|---|---|---|
| Development | 45 | 36 | 0 | 0 | 1.00 | 1.00 |
| Held-out | 12 | 7 | 0 | 0 | 1.00 | 1.00 |

**Read these numbers carefully.** The cases were written by the developers for rules the developers wrote, and the development set was tuned. Perfect scores show the engine does what its rules say, not that it will be this accurate on real marketing copy. The first run on the development set had 4 disagreements, which led to the changes listed below. A fair claim is "reliable on well-defined rule checks"; claim detection on free-form copy needs real-world testing, and the roadmap includes it.

## Changes made because of testing
| Problem found | Fix |
|---|---|
| Sentence splitter cut `99.5%` at the decimal point, quoting "5% uptime." | Custom splitter that only breaks on `.!?` followed by whitespace |
| HTML tags were counted as a very long sentence | Wording checks run on visible text; tags blanked with equal-length spaces so offsets stay valid |
| "within 1 hour" did not match a fact keyword "hours" | Keyword matching stems plural forms |
| "Read our best practices guide" flagged as an unsupported superlative | Exclusion list for ordinary phrases such as "best practices" and "best regards" |
| Two evaluation labels were wrong (a 27-word sentence labelled "long"; "Lumora logo" labelled weak alt text) | Corrected the labels; the engine behaviour was right |

## Reliability checks
Server returns structured errors for bad input, never stack traces; every write is in a transaction rolled back on failure; stale suggestions are refused (409) instead of corrupting text; invalid brand-kit rules are rejected on save; the seeding script and 47 tests run against fresh databases.


## Browser end-to-end test (real Chromium, Playwright)
Run on 21 Oct 2026 against a fresh database seeded with `seed_demo.py`. The script followed the demo flow through the real UI with the app's strict Content-Security-Policy left on: creator logs in, loads the launch-email sample (7 highlighted findings, each showing its source), accepts one suggestion (text changes, new revision), submits; reviewer tries to approve with 4 high-severity findings open (refused), requests changes; creator rewrites and re-checks (no open findings) and resubmits; reviewer approves; manager publishes; Insights, Audit log (46 rows) and AI & data pages render. Screenshots and the step log are in `docs/screenshots/` (`ui_e2e_result.json`). 15 of 16 checks passed on the first run; the one console error was the expected 409 from the approval gate.

**Defect found and fixed:** at 390px width every page scrolled sideways (scrollWidth 582) because tables overflowed their cards. Fixed with `overflow-x:auto` on `.card`; re-measured 390 on Content, Insights and Audit log.

**Still not done:** no screen-reader or keyboard-only walkthrough, no other browsers, no real users.

## What has not been verified
- The web UI has been driven in Chromium (above) but **not with a screen reader**, keyboard-only, or other browsers.
- The optional external AI module has not been run against the live API.
- No load testing. SQLite and the threaded standard-library server suit a team-sized demo, not heavy traffic.
- No usability sessions with real users have been run; see USER_TESTING_KIT.md.
