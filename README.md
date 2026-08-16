# Sagard Portfolio Metrics Extraction (crawl-phase POC)

Takes a folder of portfolio-company PDF reporting packages and extracts a small,
consistent set of metrics into a table that's easy to scan across companies and
quarters.

See [`NOTES.md`](NOTES.md) for the approach, assumptions, and next steps.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
```

## Run

```bash
python3 src/extract.py
```

Reads every PDF in `data/`, prints a coverage summary and a preview table, and
writes two files to `output/`:

- `metrics_long.csv` — one row per (company, period, metric), including the
  raw label/value text the number was extracted from, for auditability.
- `metrics_wide.csv` — one row per (company, period), metrics as columns.
  This is the "review across companies" view.

Optional flags: `--input <folder>` / `--output-dir <folder>` to point at a
different set of PDFs.

## What's extracted

Eight metrics, chosen to cover the concepts most companies in this sample
actually report: `revenue`, `arr`, `gross_margin`, `net_revenue_retention`,
`logo_churn`, `headcount`, `cash_balance`, `net_burn`. Not every metric
applies to every company (e.g. a lending business doesn't report ARR or
churn) — blank cells are expected, not extraction failures. Details on why
in `NOTES.md`.
