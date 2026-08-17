# Approach, assumptions, and next steps

## Approach

Read all 24 sample PDFs first. They're text-based (not scanned), mostly one
company per file, laid out as a header, one or two "Metric&nbsp;&nbsp;Value"
tables, and a commentary paragraph. That ruled out OCR and pointed to a
**regex/alias-based extractor** — deterministic, no API key, easy to reason
about — the right tool for a 1-2 hour crawl pass. An LLM extractor would
generalize better to metrics I didn't anticipate but trades away
reproducibility; noted as a walk-phase upgrade below.

## What's implemented

Five small modules under `src/`, each with one job:

- **`config.py`** — 8 canonical metrics, each with an ordered alias list
  (most-specific first, e.g. "Total Recognized Revenue" before "Recognized
  Revenue" so a subtotal line doesn't win), plus the filename pattern and one
  company-rename mapping.
- **`values.py`** — parses a raw token (`$12.7M`, `(0.55M)`, `148bps`,
  `96.1%`, `2.4x`) into value + unit; scans a line for the first such token
  after a matched label.
- **`pdf_parser.py`** — reads via `pdfplumber`, pulls company + period from
  the **filename** (more reliable than the body — one report states its
  period as prose instead of "Q1 2025"), applies the label-matching. Falls
  back to narrative-text regexes for headcount, where two reports disclose it
  only in prose.
- **`csv_writer.py`** — writes a long CSV (one row per metric, raw
  label/value kept for audit) and a wide CSV (one row per company-quarter),
  plus a console preview.
- **`extract.py`** — CLI entry point; orchestrates the above and prints a
  coverage summary.

## Key assumptions

- **Metric selection**: `revenue, arr, gross_margin, net_revenue_retention,
  logo_churn, headcount, cash_balance, net_burn` — the ones that actually
  recur and cover growth, profitability, retention, and liquidity. Left out
  **EBITDA**: no company in this sample discloses it, so the column would
  just be empty; a one-line alias-list change once one does.
- **Similar labels ≠ same metric**: LendBridge's "Net Charge-off Rate" is a
  credit-loss metric, not churn — not mapped, on purpose. TalentVault's Gross
  vs. Net Revenue Retention are genuinely different figures; only NRR is
  captured.
- **Relabeling across quarters**: LendBridge renames the same metric three
  ways across five quarters. Treated as equivalent only because the reports'
  own footnotes confirm it, not just similar wording.
- **Company identity across a rebrand**: FleetLink → ApexFreight is the same
  legal entity (confirmed by ApexFreight's own footnote 1). Hard-coded that
  one mapping (`COMPANY_KEY_ALIASES`) rather than auto-detecting renames —
  auto-detection from text alone is false-positive-prone and out of scope
  here.
- **Currency**: PeopleFlow reports in GBP; everyone else USD. Tagged with a
  `reporting_currency` column rather than FX-converted — there's no
  point-in-time rate in these documents, so conversion would just be a guess.
- **One value per cell**: where a table shows current + prior quarter, only
  the current period is taken — the prior quarter has its own PDF in the
  dataset, so keeping both would be redundant and complicate the schema.
- **Multi-company documents are out of scope**:
  `Portfolio_Snapshot_Q2_2025.pdf` rolls up four companies in a different
  layout. Detected and skipped explicitly (visible in the console output)
  rather than silently ignored.
- **Line-based, not table-structure-aware**: matches "alias, then a numeric
  token on the same line" — no cell/column reconstruction via `pdfplumber`.
  Clean on this sample since every row starts with its label; not robust to
  a wrapped label or a value that precedes its label.

## Result

23 of 24 PDFs processed (1 skipped, see above), 64% of the 8-metric ×
23-report grid filled. Not an extraction bug — most blanks are metrics that
genuinely don't apply (no `cash_balance`/`net_burn` for the profitable
payments/lending/freight businesses; no `arr`/`logo_churn` for
non-subscription businesses).

## If I had more time (walk / run phase)

- **LLM-assisted extraction** for the long tail: alias pass first (cheap,
  deterministic, auditable), then send only the *unmatched* metrics to an
  LLM with the raw page text — extract a value or return "not disclosed."
- **Table-structure-aware extraction** via `pdfplumber`'s `extract_tables()`
  (or a layout model), so wrapped labels and multi-column layouts aren't
  fragile.
- **Confidence scores** and a lightweight review flag, so ambiguous matches
  get a human check instead of blind trust.
- **Time-series validation**: flag quarter-over-quarter jumps outside a sane
  range.
- **A second parser for the multi-company snapshot doc** instead of skipping
  it — that pattern is presumably a real report type Sagard receives too.
- **FX normalization**, once real point-in-time rates are available.

## Presenting this

[`presentation.html`](presentation.html) covers the same ground, plus one
thing this document doesn't: a proposed (not built) architecture for running
this daily on GCP into BigQuery.
