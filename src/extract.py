"""Extract a small set of portfolio metrics from Sagard portfolio-company PDF reports.

Usage:
    python3 src/extract.py [--input data] [--output-dir output]
"""
import argparse
import csv
import glob
import os
import re

import pdfplumber

FILENAME_RE = re.compile(r"^(?P<key>.+?)_Q(?P<quarter>\d)_(?P<year>\d{4})\.pdf$", re.IGNORECASE)

# Filename keys that refer to the same underlying company across a rename.
# (Apex Freight Solutions Inc. is the rebrand of FleetLink Logistics Network,
# effective 1 April 2025 -- confirmed in ApexFreight_Q2_2025.pdf footnote 1.)
COMPANY_KEY_ALIASES = {
    "FleetLink": "ApexFreight",
}

# Multi-company roll-up documents that don't follow the single-company template
# used elsewhere (e.g. Portfolio_Snapshot_Q2_2025.pdf covers 4 companies in one
# file). Handling those would need a different parser; out of scope for this pass.
SKIP_FILE_PREFIXES = ("Portfolio_Snapshot",)

VALUE_TOKEN_RE = re.compile(
    r"^\(?-?\$?\d[\d,]*(?:\.\d+)?(?:%|bps|M|K|x)?\)?$", re.IGNORECASE
)

# Canonical metric -> ordered list of label phrasings (most specific first).
# A line is treated as a match if it starts with one of these phrases
# (case-insensitive) and a numeric token follows somewhere on the line.
METRIC_ALIASES = {
    "revenue": [
        "total recognized revenue",
        "quarterly recognized revenue",
        "quarterly revenue",
        "recognized revenue (usd)",
        "recognized revenue",
        "net revenue (usd)",
        "total billings (usd)",
        "gross transaction revenue",
        "platform revenue (recognized)",
    ],
    "arr": [
        "contracted arr (end of period)",
        "end-of-period arr",
        "arr (end of period)",
        "subscription arr (end of period)",
        "contracted annual recurring revenue",
        "contracted arr",
        "annual recurring revenue",
    ],
    "gross_margin": [
        "gross margin",
    ],
    "net_revenue_retention": [
        "net revenue retention (ltm)",
        "net revenue retention",
        "nrr (ltm)",
        "net dollar retention (ltm)",
        "net dollar retention",
        "net pound retention",
    ],
    "logo_churn": [
        "logo churn rate (ltm)",
        "logo churn (ltm)",
        "annual logo churn",
        "logo churn",
    ],
    "headcount": [
        "total headcount",
        "headcount",
    ],
    "cash_balance": [
        "cash & restricted cash",
        "cash & equivalents",
        "cash balance",
    ],
    "net_burn": [
        "monthly net burn",
        "quarterly net burn",
        "net burn",
    ],
}

# Headcount is occasionally disclosed only in narrative text rather than a
# table row (e.g. "the team ended the quarter at 199 employees").
HEADCOUNT_NARRATIVE_PATTERNS = [
    re.compile(r"ended (?:the quarter|the period) (?:at|with) (\d[\d,]*)\s+employees", re.IGNORECASE),
    re.compile(r"headcount of (\d[\d,]*)\b", re.IGNORECASE),
]


def parse_value(raw):
    """Parse a raw value token like '$12.7M', '($0.55M)', '148bps', '96.1%' into (numeric, unit)."""
    if raw is None:
        return None, None
    token = raw.strip()
    negative = token.startswith("(") and token.endswith(")")
    token = token.strip("()")
    if token.startswith("-"):
        negative = True
        token = token[1:]
    token = token.replace("$", "").replace(",", "")
    unit = None
    for suffix in ("bps", "%", "M", "K", "x"):
        if token.lower().endswith(suffix.lower()):
            unit = suffix
            token = token[: -len(suffix)]
            break
    try:
        num = float(token)
    except ValueError:
        return None, None
    if negative:
        num = -num
    return num, unit


def extract_value_after_label(line, alias):
    """If `line` starts with `alias`, return the first numeric token found after it."""
    lower = line.lower()
    if not lower.startswith(alias):
        return None
    remainder = line[len(alias):].strip()
    for tok in remainder.split():
        if VALUE_TOKEN_RE.match(tok):
            return tok
    return None


def extract_metrics_from_text(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    metrics = {}
    for canonical, aliases in METRIC_ALIASES.items():
        found_token, found_line = None, None
        for alias in aliases:
            for line in lines:
                token = extract_value_after_label(line, alias)
                if token:
                    found_token, found_line = token, line
                    break
            if found_token:
                break
        if found_token:
            value, unit = parse_value(found_token)
            metrics[canonical] = {
                "raw_label": found_line,
                "raw_value": found_token,
                "value": value,
                "unit": unit,
            }

    if "headcount" not in metrics:
        for pattern in HEADCOUNT_NARRATIVE_PATTERNS:
            m = pattern.search(text)
            if m:
                raw = m.group(1)
                value, unit = parse_value(raw)
                metrics["headcount"] = {
                    "raw_label": "(from narrative text, not a table row)",
                    "raw_value": raw,
                    "value": value,
                    "unit": unit,
                }
                break
    return metrics


def detect_currency(text):
    return "GBP" if re.search(r"\bGBP\b", text) else "USD"


def process_pdf(path):
    filename = os.path.basename(path)
    m = FILENAME_RE.match(filename)
    if not m:
        return None

    company_key = m.group("key")
    quarter = int(m.group("quarter"))
    year = int(m.group("year"))
    canonical_key = COMPANY_KEY_ALIASES.get(company_key, company_key)

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    display_name = lines[0] if lines else company_key

    return {
        "file": filename,
        "company_key": canonical_key,
        "company_display_name": display_name,
        "period": f"Q{quarter} {year}",
        "quarter": quarter,
        "year": year,
        "reporting_currency": detect_currency(text),
        "metrics": extract_metrics_from_text(text),
    }


def write_long_csv(path, records):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "company_key", "company_display_name", "period", "reporting_currency",
            "metric", "raw_label", "raw_value", "value", "unit", "source_file",
        ])
        for r in records:
            for metric_name in METRIC_ALIASES:
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
                    row.append(f"{info['value']}{info['unit'] or ''}")
                else:
                    row.append("")
            writer.writerow(row)


def print_preview(records, metric_names, limit=8):
    header = ["company", "period"] + metric_names
    widths = [max(len(h), 10) for h in header]
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data", help="Folder of PDF reports")
    parser.add_argument("--output-dir", default="output", help="Where to write CSVs")
    args = parser.parse_args()

    pdf_paths = sorted(glob.glob(os.path.join(args.input, "*.pdf")))
    os.makedirs(args.output_dir, exist_ok=True)

    records, skipped = [], []
    for path in pdf_paths:
        filename = os.path.basename(path)
        if filename.startswith(SKIP_FILE_PREFIXES):
            skipped.append(f"{filename} (multi-company roll-up doc, not single-company template)")
            continue
        record = process_pdf(path)
        if record:
            records.append(record)
        else:
            skipped.append(f"{filename} (filename doesn't match <Company>_Q<n>_<year>.pdf)")

    records.sort(key=lambda r: (r["company_key"], r["year"], r["quarter"]))
    metric_names = list(METRIC_ALIASES.keys())

    long_path = os.path.join(args.output_dir, "metrics_long.csv")
    wide_path = os.path.join(args.output_dir, "metrics_wide.csv")
    write_long_csv(long_path, records)
    write_wide_csv(wide_path, records, metric_names)

    total_cells = len(records) * len(metric_names)
    filled_cells = sum(1 for r in records for m in metric_names if m in r["metrics"])

    print(f"Processed {len(records)} reports ({len(skipped)} skipped)")
    for s in skipped:
        print(f"  skipped: {s}")
    print(f"Metric coverage: {filled_cells}/{total_cells} ({filled_cells / total_cells:.0%}) cells filled\n")
    print_preview(records, metric_names)
    print(f"\nWrote {long_path}")
    print(f"Wrote {wide_path}")


if __name__ == "__main__":
    main()
