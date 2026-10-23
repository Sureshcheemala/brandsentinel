# Privacy, security, accessibility and responsible design

## Human control
- No suggestion is applied unless the owner clicks Accept; judgement-heavy suggestions (claims, sentence splitting, logos) are manual only.
- Findings with weak grounding are labelled **needs human judgement**. Unverified statistics are never declared false.
- Dismissals need a written reason and are recorded. High-severity dismissals need a reviewer who is not the author.
- Authors cannot approve their own work. Approval is blocked while high-severity findings are open unless a manager or admin records an override reason, which is audited.
- Every decision (accept, dismiss, approve, override, publish, brand-kit edit) is in the audit log.

## Explainability
Each finding shows the quoted evidence, why it was raised, and the exact guideline or approved fact (id, title, excerpt). Findings are reproducible: the revision stores the brand-kit version it was checked against. A downloadable report lists findings, history and comments.

## Privacy and confidentiality
- Content, brand kit and audit data are stored in a local SQLite file; nothing is sent elsewhere by default.
- Role-based visibility: creators see only their own items; reviewers see items once submitted; managers and admins see all. Drafts are private.
- Uploaded .docx files are reduced to extracted text and the original file is not retained. Images are stored only to display them to permitted viewers.
- Passwords are hashed (PBKDF2-SHA256, per-user salt); sessions expire after 8 hours; 5 failed logins in 5 minutes block further attempts for that account.
- Demo data is a fictional brand. No real confidential data is needed to run or demo.

## Disclosure of AI and external services
- The product's findings come from a rules engine, not a model.
- An optional external AI tone opinion exists in `app/llm.py`. It is **off by default** and turns on only when `BS_EXTERNAL_AI=on` and `ANTHROPIC_API_KEY` are both set. When on, only the draft text and the voice guideline text are sent, never the brand library, assets, user data or other items. Its findings are labelled "AI-assisted", always need human judgement, must quote text that exists verbatim in the draft, and are never auto-applied. The UI's **AI & data** page and every review report state whether it was used. This module has not been run against the live API in the build environment, so treat it as untested.
- Development used an AI coding assistant; see DISCLOSURES.md.

## Security measures implemented
- Parameterised SQL everywhere; JSON size limit 6 MB, file limit 4 MB, type allowlist (.docx, PNG, JPG, SVG), content length limits.
- Strict CSP (`default-src 'self'`), `X-Content-Type-Options`, `X-Frame-Options: DENY`, no inline scripts, UI uses `textContent`.
- SVG files are served with `Content-Security-Policy: sandbox`; static file serving blocks path traversal; errors never leak internals.
- Brand-kit regexes are validated on save so a bad rule cannot crash reviews.
- Not yet covered (see roadmap): HTTPS termination, CSRF tokens (bearer tokens are used instead of cookies), regex-complexity limits for admin-supplied patterns, antivirus scanning of uploads, SSO.

## Accessibility of the product itself
Semantic headings and labels, skip link, keyboard-operable controls, visible focus ring, severity shown as text and not colour alone, a live region for status messages. Not yet verified with a screen reader or an automated audit; the warnings below apply. Automated checks cover only part of WCAG, so BrandSentinel does not certify compliance.

## Fairness and language limits
Checks are written for English. Tone is judged against the organisation's own written voice rules, not a generic standard. Other languages are unsupported until tested.
