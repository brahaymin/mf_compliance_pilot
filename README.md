# MF Feedback Pilot

Static MF Feedback Pilot for browsing **structured** mutual-fund sales-charge waiver, ROA, LOI, breakpoint, and waiver-limitation excerpts from public SEC EDGAR filings.

## Live site

The live MF Feedback Pilot is the Vercel site:

https://mfcompliancepilot.vercel.app/

Names Rule (front page): https://mfcompliancepilot.vercel.app/

Rules sample: https://mfcompliancepilot.vercel.app/rules.html

Free guide (priorities): https://mfcompliancepilot.vercel.app/priorities.html

Family contacts: https://mfcompliancepilot.vercel.app/family-contacts.html

Library coverage: https://mfcompliancepilot.vercel.app/coverage.html

`names.html` and old `index.html?issue=…` links redirect to the right page.

Merging to `main` auto-deploys that Vercel project (GitHub commit statuses report it as `mf_compliance_pilot`; the public URL is unchanged). Pull requests typically get a Vercel preview deployment.

The older GitHub Pages copy at https://brahaymin.github.io/mf_compliance_pilot/ is retired. A redirect stub lives in `docs/` (meta refresh plus a link to the Vercel site). After merge, set Pages to **Deploy from a branch**, branch `main`, folder `/docs`. Do not delete the repository or disable Pages. Until that setting is changed, Pages still publishes the repository root.

## What’s included

| File | Role |
| --- | --- |
| `index.html` / `pilot.css` / `pilot.js` | Unified rule browser (landing page): search and filter structured rules by issue, family, category, status, and keyword, with version timelines, EDGAR identifiers, and coverage gaps |
| `issue_map.json` | Documented issue → category / waiver_type / keyword mapping |
| `rules.html` | Redirects to `index.html`, preserving the query string (for example `?issue=…`) |
| `priorities.html` / `priorities.css` / `priorities.js` | Compliance priorities and feature guide |
| `priorities_ideas.json` / `priorities_demo_stats.json` | Priorities list and public-sample illustrations |
| `family-contacts.html` / `family-contacts.css` / `family-contacts.js` | Prospectus contact types by family, linking to the public SEC source filing (no individual names, e-mails, phones, or mailing addresses) |
| `family_contacts.json` | Sanitized contact-type cards per sample family (counts and source filings; allowlisted institutional websites only) |
| `coverage.html` / `coverage.css` / `coverage.js` | Library coverage tables (counts by year, form type, and fund family) |
| `coverage_slices.json` | Read-only aggregate export from the local SQLite library |
| `names.html` / `names.css` / `names.js` | Names Rule 80% policy pilot table (fund name, series ID, filing date, form, policy sentence, EDGAR link) |
| `names_policy80.json` | Pilot extract of 80% investment-policy rows from public SEC EDGAR filings |
| `structured_rules_sample.json` | Privacy-screened Guggenheim structured sample (deduped by logical rule; tickers merged), with Current/Historical status, filing dates, days since prior filing, supersession/amendment links and version timelines |
| `sample_rules.json` | Legacy regex-snippet sample (secondary tab) |
| `scripts/refresh_pilot_data.py` | Read-only refresh: writes coverage slices, sanitizes contacts, runs the PII screen, and enforces the static size cap |
| `scripts/pii_screen.py` | Existing pilot privacy screen (same patterns as the private pipeline exporter) |
| `docs/` | GitHub Pages redirect stub to the Vercel site |
| `.nojekyll` | Serve files as plain static assets |

## Current vs historical

Every rule card shows a solid green **CURRENT** or red **HISTORICAL** badge. Open `?status=historical` or `?status=all` to change the default filter. Open `?issue=breakpoints` (or another issue id from `issue_map.json`) to start with that regulatory issue selected. Assets are cache-busted with `?v=` (see `data-asset-version` in `index.html`).

Rules from each ticker's latest 485BPOS are Current; earlier versions are Historical. A later 497 that changes the wording supersedes the 485BPOS version (shown as "Amended by" / "Superseded by"). The Status filter defaults to Current.

## Caveats

- The structured rule browser is still the Guggenheim family (including New Age Alpha successor filings) plus a Fidelity sample slice. Static sample for demos — **not** a complete live library. Library-wide counts on the coverage page come from the local database and will grow as backfill continues.
- Automated extraction is **unreviewed** and is **not legal advice**.
- Public regulatory fields and aggregates only. No live SQL, API, or authentication. Shipped data must stay under about 25 MB raw / 3 MB gzipped.
- Individual names, e-mails, phone numbers, and mailing addresses from filing contacts are not published.

## Refreshing the static slices

The live database stays on the local box and is opened read-only:

```bash
python3 scripts/refresh_pilot_data.py --db /path/to/mf_compliance.db
python3 -m pytest -q
```

The script is deterministic for a given database snapshot (sorted JSON, no wall-clock timestamp). It does not write the database, and it does not read credentials or identity files. Optional `--structured-exporter` can rebuild `structured_rules_sample.json` with the private pipeline exporter; that is off by default so the sample stays inside the size cap.

### Weekly Names update (part of the refresh)

The weekly Names job hands its new `names_policy80.json` to the refresh:

```bash
python3 scripts/refresh_pilot_data.py --skip-db --names-json /path/to/candidate/names_policy80.json
```

The candidate is published only if the Names shape gate (`scripts/names_gate.py`) and the PII screen both pass; otherwise the refresh exits non-zero and the published file is untouched. The refresh also re-renders the shared page chrome so the Names accuracy line always matches `meta.review_score`. CI runs the same gates on every PR and push.

## Shared chrome, accuracy and uptime

- `scripts/site_chrome.py` writes the shared header, banner, accuracy status and footer into every tab (`--check` fails when stale). Styles: `site.css`.
- `scripts/uptime_check.py` + `.github/workflows/uptime.yml`: hourly free check of every live tab (non-200 or missing content fails the run).
- Draft terms and privacy text are kept privately off-repo until lawyer review (not published).

## Local preview

```bash
python -m http.server 8765 --directory .
```
