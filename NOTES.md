# Approach, assumptions, and next steps

## How I approached it

I first read all 24 sample PDFs to see how messy "messy" actually is before
designing anything. They're text-based (not scanned), one company per file
(mostly), laid out as a short header, one or two "Metric &nbsp; Value [Value]"
tables, and a paragraph of commentary. That ruled out OCR as a concern and
made a **regex/alias-based extractor** the right tool for a 1-2 hour "crawl"
pass — it's fully deterministic, needs no API key, and is easy to reason
about and extend. An LLM-based extractor would likely generalize better to
metrics I didn't anticipate, but trades away reproducibility and adds a
dependency; I've noted it as a natural "walk" phase upgrade below.

## What I implemented

`src/extract.py`:

1. Reads each PDF's text with `pdfplumber`.
2. Pulls company + period from the **filename** (`<Company>_Q<n>_<year>.pdf`),
   which turned out to be more reliable than parsing it from the document
   body — one report (`MediSight_Q1_2025.pdf`) states its period as "Quarter
   ended March 31, 2025" instead of "Q1 2025", so text-based period parsing
   would need its own date→quarter logic for no real benefit here.
3. For each of 8 canonical metrics, tries an ordered list of label phrasings
   against every line of the document (e.g. `net_revenue_retention` matches
   "Net Revenue Retention (LTM)", "NRR (LTM)", "Net Dollar Retention", "Net
   Pound Retention", ...). First match wins, aliases are ordered
   most-specific-first (e.g. "Total Recognized Revenue" is checked before
   "Recognized Revenue" so a subtotal line like "Recognized Revenue
   (transaction)" doesn't win over the real total).
4. Parses the matched value (`$12.7M`, `(0.55M)`, `148bps`, `96.1%`, `2.4x`)
   into a numeric value + unit, handling `$`, commas, and parenthesized
   negatives.
5. Falls back to a couple of narrative-text regexes for headcount, since two
   reports disclose it only in prose ("...ended the period with 114
   employees...") rather than in a table.
6. Writes a long-format CSV (one row per metric, with the raw label/value it
   came from, for auditability) and a wide-format CSV (one row per
   company-quarter, metrics as columns) for at-a-glance review.

## Key assumptions

- **Metric selection.** I picked `revenue, arr, gross_margin,
  net_revenue_retention, logo_churn, headcount, cash_balance, net_burn`
  because they're the ones that actually recur across this sample and cover
  growth, profitability, retention, and liquidity. I deliberately left out
  **EBITDA** — no company in this sample discloses it (closest analogues are
  Gross Margin / Pre-Provision Operating Margin, which aren't directly
  comparable), so an EBITDA column would just be empty everywhere; adding it
  is a one-line alias-list change once a report that discloses it shows up.
- **Not every "similar" label means the same metric.** LendBridge's "Net
  Charge-off Rate" is a credit-loss metric, not customer churn, even though
  it shares a table position with `logo_churn` elsewhere — I did not map it
  in, on purpose. Similarly TalentVault's "Gross Revenue Retention" and "Net
  Revenue Retention" are genuinely different figures; only NRR is captured.
- **Relabeling across quarters, same company.** LendBridge alone renames the
  same metric three ways across five quarters ("Pre-Provision Operating
  Margin" → "Adjusted Operating Margin", "Net Charge-off Rate" ↔ "Credit Loss
  Rate") — the alias list treats these as equivalent based on the reports'
  own footnotes confirming equivalence, not just similar wording.
- **Company identity across a rebrand.** `FleetLink_Q4_2024.pdf` /
  `FleetLink_Q1_2025.pdf` and `ApexFreight_Q2_2025.pdf` are the same legal
  entity (confirmed by ApexFreight's own footnote 1). I hard-coded that one
  mapping (`COMPANY_KEY_ALIASES`) rather than trying to auto-detect renames —
  auto-detecting company identity across a name change from text alone is a
  genuinely hard, false-positive-prone problem and out of scope for a crawl
  phase.
- **Currency.** PeopleFlow reports in GBP (stated explicitly in its header);
  everyone else is USD. I tag each row with a `reporting_currency` column
  rather than attempting FX conversion — cross-currency comparison needs a
  point-in-time FX rate, which isn't in these documents and would just be a
  guess.
- **One value per cell.** Where a table shows both the current and prior
  quarter (many do), I take the current-period value only — the prior-quarter
  column is redundant once you have the prior quarter's own PDF in the
  dataset, and mixing periods into one cell would complicate the schema for
  no benefit.
- **Multi-company documents are out of scope.** `Portfolio_Snapshot_Q2_2025.pdf`
  rolls up four companies into a single file with a different layout than
  the standalone per-company reports. Rather than special-case it, the
  pipeline detects and skips it explicitly (visible in the run's console
  output) — silently ignoring it would be worse than flagging it.
- **Extraction is line-based, not table-structure-aware.** I match on "line
  starts with alias, followed by a numeric token somewhere on the line" — no
  attempt to reconstruct actual table cell/column boundaries from
  `pdfplumber`. It worked cleanly on this sample because every metric table
  row happens to start with its label, but it isn't robust to a report where
  the label wraps onto a second line or a value precedes its label.

## Result

23 of 24 PDFs processed (1 explicitly skipped, see above), 64% of the
8-metric × 23-report grid filled. That's not an extraction bug — many blanks
are metrics that genuinely don't apply to that company (e.g. no
`cash_balance`/`net_burn` for the profitable payments/lending/freight
businesses; no `arr`/`logo_churn` for non-subscription businesses).

## If I had more time (walk / run phase)

- **LLM-assisted extraction** for the long tail: run the alias-based pass
  first (cheap, deterministic, auditable), then send only the *unmatched*
  metrics for a company/period to an LLM with the raw page text, asking it to
  either extract a value or explicitly return "not disclosed." Keeps the
  cheap path fast and reserves the expensive path for genuine ambiguity.
- **Table-structure-aware extraction** using `pdfplumber`'s
  `extract_tables()` (or a layout model) instead of line-text regex, so
  multi-line labels and multi-column layouts are less fragile.
- **Confidence scores** and a lightweight review UI (or just a "needs review"
  CSV column) so a human can quickly confirm ambiguous matches instead of
  trusting the pipeline blindly.
- **Time-series validation**: flag quarter-over-quarter jumps outside a
  sane range as a cheap sanity check.
- **Handle the multi-company snapshot doc** with a second parser instead of
  skipping it, since that pattern (a rolled-up cross-portfolio summary) is
  presumably also a real report type Sagard receives.
- **FX normalization** to a reporting currency, once real FX rates are
  available for the relevant periods.
