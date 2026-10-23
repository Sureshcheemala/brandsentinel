# BrandSentinel: final report (Round 3)

## 1. Problem
Brand guidelines exist in most organisations but are rarely enforced before publication, and content now comes from employees, agencies and AI tools. Public research the team found (vendor-published, to be verified at source): 81% of companies deal with off-brand content; 85% have guidelines but about 30% consistently enforce them; 36.5% of marketers say AI errors reached the public; 94.8% of home pages have detectable WCAG failures. Unsupported promotional claims draw regulatory complaints (India's ASCI examined 10,093 complaints in 2023-24).

## 2. Users
Creators (marketing, agencies, regional staff), brand managers, compliance reviewers, guideline owners, admins. Setting: between drafting tools and publishing channels.

## 3. Solution
A review layer that checks a draft against the approved brand kit and returns explained, sourced findings with suggestions that keep the author's intent. Humans accept, edit or dismiss; reviewers and managers approve; everything is tracked.

## 4. Workflow
Submit → check → explain → creator decides → review (comments, request changes) → approve (high-severity findings block unless a manager records an override) → publish → insights feed back to guideline owners. See ARCHITECTURE.md for the state machine and role table.

## 5. What was built (all runs locally; no third-party packages)
- Rules engine: terminology, tone, claims against approved facts (with expiry), offer disclaimers, alt text, link text, WCAG contrast, palette, logo variant and proportions, image size.
- Formats: text, Markdown, HTML, .docx, PNG/JPG/SVG.
- Workflow: roles, comments, revisions with diffs, approvals, overrides, publishing, audit log, downloadable review report.
- Insights: repeated mistakes by rule and team, accepted vs dismissed counts, "possibly unclear" guideline signal, average revisions to approval.
- Governance: versioned brand kit editable by admin, AI and data disclosure page, optional external AI (off by default).

## 6. Technology
Python standard library (http.server, sqlite3, zipfile), vanilla JavaScript UI, JSON brand kit, Docker file. Rationale in ARCHITECTURE.md.

## 7. Evidence of quality
47 automated tests pass. Rules engine scored 36/36 expected findings with 0 false alarms on the 45-case development set and 7/7 with 0 false alarms on 12 held-out cases, with the caveat that cases were written by the developers (TESTING.md). Four real defects found by evaluation were fixed. **No real-user testing has been completed; the kit is in USER_TESTING_KIT.md.** Add real results here before submitting.

## 8. Impact (hypotheses, to be measured)
Fewer review rounds, faster time from draft to approval, fewer unsupported claims reaching reviewers, and a ranked list of unclear guidelines. The demo data shows the mechanism works; it does not prove the size of the effect.

## 9. Privacy, security, accessibility, responsible design
See RESPONSIBLE_AI.md.

## 10. Limitations and roadmap
See LIMITATIONS_ROADMAP.md.

## 11. The three improvements (declared in Round 1, status)
| Improvement | Status in this build |
|---|---|
| Accuracy measured on a labelled set, false positives driving tuning | Done for rule checks (evaluation/); extend with real copy |
| Image and layout checks beyond contrast and alt text | Partly: logo variant and proportions, palette, resolution; no pixel analysis |
| Guideline-clarity report | Done in basic form (dismissal-rate signal on the Insights page) |
