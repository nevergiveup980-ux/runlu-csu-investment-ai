# RUNLU INVEST — standalone deployment checklist

## Security boundary
This repository contains private CSU-specific records in other files. **Never publish this repository's entire `public/` folder**, copy its `portfolio.json`, or use a GitHub Pages job from this repository for INVEST. The original CSU Pages workflow remains on `main`.

## Standalone release
1. Create a **new empty repository** named `runlu-invest` (prefer private during preparation).
2. Copy **only** `public/index.html` from branch `runlu-invest-v0.1` into the new repository as `index.html`. Review the file before publication; do not include any other source files, personal portfolios, tokens, or credentials.
3. Set up independent static hosting for the new repository. Use a dedicated URL such as `invest.runlu.ca` only after verifying DNS and deployment ownership. Do not point both products at the same Pages site.
4. Verify the page title and visible heading say RUNLU INVEST, no CSU-only dashboard appears, and browser developer tools show no requests for `portfolio.json`.
5. Confirm Watchlist, Portfolio, local JSON export/import, mobile controls and no-trading behavior in a fresh browser. Do not import real personal records into public demo environments.
6. Only after successful validation, add the independent public URL to RUNLU's main website.

## Browser storage warning
Data is stored in localStorage, scoped to the exact site origin. Moving to a new hostname **does not transfer** existing notes. Export a JSON backup from the old origin, then import it at the new one; do not promise automatic synchronization.

## Release gate
Do not re-enable `.github/workflows/invest-preview-pages.yml` in the CSU repository. Its shared Pages target conflicts with the CSU deployment.
