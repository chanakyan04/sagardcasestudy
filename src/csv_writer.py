"""Turns a list of parsed records into the two output CSVs, plus a console preview."""
import csv

from config import METRIC_ALIASES


def write_long_csv(path, records):
    """One row per (company, period, metric) -- includes the raw source text for auditability."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "company_key", "company_display_name", "period", "reporting_currency",
            "metric", "raw_label", "raw_value", "value", "unit", "source_file",
        ])
        for r in records:
            for metric_name in METRIC_ALIASES:  # Always emit a row for every metric, even if it's blank.
                info = r["metrics"].get(metric_name)
                writer.writerow([
                    r["company_key"], r["company_display_name"], r["period"], r["reporting_currency"],
                    metric_name,
                    info["raw_label"] if info else "",
                    info["raw_value"] if info else "",
                    info["value"] if info else "",
                    info["unit"] if info else "",
                    r["file"],
                ])


def write_wide_csv(path, records, metric_names):
    """One row per (company, period), metrics as columns -- the "review across companies" view."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["company_key", "company_display_name", "period", "reporting_currency", "source_file"]
            + metric_names
        )
        for r in records:
            row = [r["company_key"], r["company_display_name"], r["period"], r["reporting_currency"], r["file"]]
            for metric_name in metric_names:
                info = r["metrics"].get(metric_name)
                if info and info["value"] is not None:
                    row.append(f"{info['value']}{info['unit'] or ''}")  # e.g. "9.3M", "121.0%"
                else:
                    row.append("")  # Missing metric -- left blank rather than "N/A" so it stays CSV/numeric-friendly.
            writer.writerow(row)


def print_preview(records, metric_names, limit=8):
    """Print a readable ASCII table of the first `limit` rows, so you can sanity-check without opening the CSV."""
    header = ["company", "period"] + metric_names
    widths = [max(len(h), 10) for h in header]  # Column width = header length, minimum 10 chars.

    print(" | ".join(h.ljust(w) for h, w in zip(header, widths)))
    print("-+-".join("-" * w for w in widths))

    for r in records[:limit]:
        row = [r["company_key"], r["period"]]
        for m in metric_names:
            info = r["metrics"].get(m)
            row.append(f"{info['value']}{info['unit'] or ''}" if info and info["value"] is not None else "-")
        print(" | ".join(str(c).ljust(w) for c, w in zip(row, widths)))

    if len(records) > limit:
        print(f"... ({len(records) - limit} more rows in output/metrics_wide.csv)")
