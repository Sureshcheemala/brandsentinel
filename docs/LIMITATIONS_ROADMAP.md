# Known limitations and roadmap

## Limitations
1. English only; rules are keyword and pattern based, so paraphrased claims ("twice as reliable") are not detected, and a sentence mentioning an approved keyword plus a different number can be a false match.
2. Claim matching is deliberately conservative: unmatched statistics are flagged "unverified" for a human, which may over-flag.
3. Visual checks are metadata-based (filenames, declared sizes, declared colours, HTML inline styles). There is no pixel analysis, so a logo pasted into an image, off-brand fonts, layout or imagery tone are not judged.
4. Word documents: text and image alt text only. Fonts, colours and embedded styles are not read, and the original file is not retained, so suggestions apply to the extracted text.
5. PDF and video are not supported.
6. Contrast is checked only where colours are declared (HTML inline styles or a `[colors: …]` line).
7. SQLite, single process, bearer tokens kept in browser session storage, no SSO or HTTPS termination.
8. The tone check is not a judge of voice quality; an optional external AI opinion exists but is untested live.
9. The UI uses browser prompts for dismissal reasons, and has not been tested with assistive technology.

## Roadmap
| Phase | Work |
|---|---|
| Next | Real-user testing on live copy; extend the labelled set to 300+ cases; add synonyms and paraphrase detection for claims; browser and screen-reader test pass |
| Soon | Pixel-level checks (dominant colours, logo clear space, text-in-image OCR); PDF input; CSS stylesheet parsing; multilingual rules |
| Integration | Google Docs and Word add-ins, CMS and social scheduler publish hooks, Slack/email notifications, SSO (SAML/OIDC) |
| Scale | Postgres, background workers, retrieval over long guideline documents, per-workspace encryption keys, antivirus scanning |
| Governance | Rule owners and review dates, A/B comparison of guideline wording, trend reports per team, exportable audit evidence |
