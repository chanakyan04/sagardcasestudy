"""Extract a small set of portfolio metrics from Sagard portfolio-company PDF reports.

This is the entry point / orchestrator: it wires together the PDF parsing
(pdf_parser.py), the metric definitions (config.py), and the CSV output
(csv_writer.py). Run it directly:

    python3 src/extract.py [--input data] [--output-dir output]
"""
import argparse
import glob
import os
from datetime import datetime, timezone

from config import SKIP_FILE_PREFIXES, METRIC_ALIASES
from pdf_parser import process_pdf
from csv_writer import write_long_csv, write_wide_csv, print_preview


def main():
    # Define the two CLI flags this script accepts, both optional.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data", help="Folder of PDF reports")
    parser.add_argument("--output-dir", default="output", help="Where to write CSVs")
    args = parser.parse_args()  # Read sys.argv and populate args.input / args.output_dir.

    pdf_paths = sorted(glob.glob(os.path.join(args.input, "*.pdf")))  # Every PDF in the input folder, alphabetical.
    os.makedirs(args.output_dir, exist_ok=True)  # Ensure the output folder exists (no-op if it already does).

    records, skipped = [], []  # records: successfully parsed reports. skipped: filenames we didn't process, with why.
    for path in pdf_paths:
        filename = os.path.basename(path)  # Just the filename, e.g. "ApexFreight_Q2_2025.pdf", not the full path.
        if filename.startswith(SKIP_FILE_PREFIXES):
            # Multi-company roll-up docs (e.g. Portfolio_Snapshot_*) don't fit the single-company template; skip them.
            skipped.append(f"{filename} (multi-company roll-up doc, not single-company template)")
            continue
        record = process_pdf(path)  # Parse company/period/metrics out of this one PDF.
        if record:
            records.append(record)
        else:
            # process_pdf returns None when the filename doesn't match <Company>_Q<n>_<year>.pdf.
            skipped.append(f"{filename} (filename doesn't match <Company>_Q<n>_<year>.pdf)")

    records.sort(key=lambda r: (r["company_key"], r["year"], r["quarter"]))  # Group by company, then chronological.
    metric_names = list(METRIC_ALIASES.keys())  # The 8 canonical metric names, in declaration order.
    inserted_at = datetime.now(timezone.utc).isoformat()  # One timestamp for the whole run, stamped on every row.

    long_path = os.path.join(args.output_dir, "metrics_long.csv")
    wide_path = os.path.join(args.output_dir, "metrics_wide.csv")
    write_long_csv(long_path, records, metric_names, inserted_at)  # One row per (company, year, quarter, metric) — auditable, includes raw source text.
    write_wide_csv(wide_path, records, metric_names, inserted_at)  # One row per (company, year, quarter) — easier to scan across companies.

    total_cells = len(records) * len(metric_names)  # Size of the full company-period x metric grid.
    filled_cells = sum(1 for r in records for m in metric_names if m in r["metrics"])  # How many cells we actually got a value for.
    pct = f"{filled_cells / total_cells:.0%}" if total_cells else "0%"  # No reports parsed -> nothing to divide by.

    print(f"Processed {len(records)} reports ({len(skipped)} skipped)")
    for s in skipped:
        print(f"  skipped: {s}")  # Explain each skip so it's visible, not silent.
    print(f"Metric coverage: {filled_cells}/{total_cells} ({pct}) cells filled\n")
    print_preview(records, metric_names)  # Quick on-screen look at the first few rows without opening the CSV.
    print(f"\nWrote {long_path}")
    print(f"Wrote {wide_path}")


if __name__ == "__main__":
    main()
