# MF Compliance Pilot (public demo)

Static partner pilot for browsing **structured** mutual-fund sales-charge waiver, ROA, LOI, breakpoint, and waiver-limitation excerpts from public SEC EDGAR filings.

## Live site

https://brahaymin.github.io/mf_compliance_pilot/

Priorities and feature guide: https://brahaymin.github.io/mf_compliance_pilot/priorities.html

Family contacts: https://brahaymin.github.io/mf_compliance_pilot/family-contacts.html

## What’s included

| File | Role |
| --- | --- |
| `index.html` / `pilot.css` / `pilot.js` | Search UI (structured rules default; legacy snippets tab) |
| `priorities.html` / `priorities.css` / `priorities.js` | Compliance priorities and feature guide |
| `priorities_ideas.json` / `priorities_demo_stats.json` | Priorities list and public-sample illustrations |
| `family-contacts.html` / `family-contacts.css` / `family-contacts.js` | Institutional fund-family contacts from prospectus filings |
| `family_contacts.json` | One compact contact card per sample family (shareholder services, retirement, intermediary, fund offices) |
| `structured_rules_sample.json` | Privacy-screened Guggenheim structured sample (deduped by logical rule; tickers merged), with Current/Historical status, filing dates, days since prior filing, supersession/amendment links and version timelines |
| `sample_rules.json` | Legacy regex-snippet sample (secondary tab) |
| `.nojekyll` | Serve files as plain static assets |

## Current vs historical

Every rule card shows a solid green **CURRENT** or red **HISTORICAL** badge. Open `?status=historical` or `?status=all` to change the default filter. Assets are cache-busted with `?v=` (see `data-asset-version` in `index.html`).

Rules from each ticker's latest 485BPOS are Current; earlier versions are Historical. A later 497 that changes the wording supersedes the 485BPOS version (shown as "Amended by" / "Superseded by"). The Status filter defaults to Current.

## Caveats

- Coverage is the full Guggenheim family (including New Age Alpha successor filings) plus a Fidelity sample slice. Static sample for demos — **not** a complete live library.
- Automated extraction is **unreviewed** and is **not legal advice**.
- Public regulatory fields only.

## Local preview

```bash
python -m http.server 8765 --directory .
```
