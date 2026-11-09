# MF Compliance Pilot (public demo)

Static partner pilot for browsing a **sample** of mutual-fund sales-charge waiver excerpts extracted from public SEC EDGAR filings.

## Live site

After GitHub Pages is enabled on this repo: https://brahaymin.github.io/mf_compliance_pilot/

## What’s included

| File | Role |
| --- | --- |
| `index.html` | Search UI |
| `pilot.css` / `pilot.js` | Styles and client-side search |
| `sample_rules.json` | Privacy-screened static sample (public fund metadata + snippets only) |
| `.nojekyll` | Serve files as plain static assets |

## Caveats

- One-time static sample for demos — **not** a complete live library.
- Automated regex-extracted text is **unreviewed** and is **not legal advice**.
- Fund `family` was not populated in the export source; search by fund name or ticker.
- Contains only public regulatory fields (ticker, fund name, description, snippet, form, filing date, accession, SEC URL).

## Local preview

```bash
python -m http.server 8765 --directory .
```

Open http://127.0.0.1:8765/
