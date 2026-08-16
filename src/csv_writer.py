"""Turns a list of parsed records into the two output CSVs, plus a console preview."""
import csv


def format_metric(info, blank=""):
    """Render one extracted metric as display text, e.g. "9.3M" / "121.0%"; `blank` if absent."""
    if not info or info["value"] is None:
        return blank
    return f"{info['value']}{info['unit'] or ''}"


def write_long_csv(path, records, metric_names):
    """One row per (company, period, metric) -- includes the raw source text for auditability."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "company_key", "company_display_name", "period", "reporting_currency",
            "metric", "raw_label", "raw_value", "value", "unit", "source_file",
        ])
        for r in records:
            for metric_name in metric_names:  # Always emit a row for every metric, even if it's blank.
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
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["company_key", "company_display_name", "period", "reporting_currency", "source_file"]
            + metric_names
        )
        for r in records:
            row = [r["company_key"], r["company_display_name"], r["period"], r["reporting_currency"], r["file"]]
            # Missing metrics are left blank rather than "N/A" so the column stays CSV/numeric-friendly.
            row += [format_metric(r["metrics"].get(m)) for m in metric_names]
            writer.writerow(row)


def print_preview(records, metric_names, limit=8):
    """Print a readable ASCII table of the first `limit` rows, so you can sanity-check without opening the CSV."""
    header = ["company", "period"] + metric_names
    rows = [
        [r["company_key"], r["period"]] + [format_metric(r["metrics"].get(m), blank="-") for m in metric_names]
        for r in records[:limit]
    ]

    # Size each column to the widest cell actually printed, so long company names
    # don't push the rest of the row out of alignment.
    widths = [max(len(h), *(len(row[i]) for row in rows)) if rows else len(h) for i, h in enumerate(header)]

    print(" | ".join(h.ljust(w) for h, w in zip(header, widths)))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(" | ".join(c.ljust(w) for c, w in zip(row, widths)))

    if len(records) > limit:
        print(f"... ({len(records) - limit} more rows in the wide CSV)")
