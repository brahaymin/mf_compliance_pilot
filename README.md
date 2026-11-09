# MF Compliance Pilot (public demo)

Static partner pilot for browsing **structured** mutual-fund sales-charge waiver, ROA, LOI, breakpoint, and waiver-limitation excerpts from public SEC EDGAR filings.

## Live site

https://brahaymin.github.io/mf_compliance_pilot/

## What’s included

| File | Role |
| --- | --- |
| `index.html` / `pilot.css` / `pilot.js` | Search UI (structured rules default; legacy snippets tab) |
| `structured_rules_sample.json` | Privacy-screened Guggenheim structured sample (deduped by logical rule; tickers merged) |
| `sample_rules.json` | Legacy regex-snippet sample (secondary tab) |
| `.nojekyll` | Serve files as plain static assets |

## Caveats

- Guggenheim-only in the structured export (one trust currently populated).
- Static sample for demos — **not** a complete live library.
- Automated extraction is **unreviewed** and is **not legal advice**.
- Public regulatory fields only.

## Local preview

```bash
python -m http.server 8765 --directory .
```
