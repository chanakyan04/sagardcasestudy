"""Reads one PDF report and turns it into a structured record.

This is where PDF text (via pdfplumber), the metric alias table (config.py),
and the value-token parsing (values.py) all come together.
"""
import os
import re

import pdfplumber

from config import FILENAME_RE, COMPANY_KEY_ALIASES, METRIC_ALIASES, HEADCOUNT_NARRATIVE_PATTERNS
from values import parse_value, extract_value_after_label


def extract_metrics_from_text(text):
    """Scan `text` for each canonical metric in METRIC_ALIASES, returning whatever it finds."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]  # Drop blank lines up front.
    metrics = {}

    for canonical, aliases in METRIC_ALIASES.items():
        found_token, found_line = None, None

        # Try each known label phrasing, most specific first, against every line,
        # and stop at the first hit -- we only want one value per metric per document.
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
                "raw_label": found_line,   # The exact source line, kept for auditability.
                "raw_value": found_token,  # The exact source token, before parsing.
                "value": value,
                "unit": unit,
            }

    # Headcount is sometimes only mentioned in a sentence, not a table row.
    # Only fall back to narrative text if the table-based pass above found nothing.
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
    """Reports are USD unless they explicitly say otherwise (e.g. PeopleFlow states 'Reporting Currency: GBP')."""
    return "GBP" if re.search(r"\bGBP\b", text) else "USD"


def process_pdf(path):
    """Read one PDF file and return a dict with its company, period, currency, and extracted metrics.

    Returns None if the filename doesn't match the expected <Company>_Q<n>_<year>.pdf pattern.
    """
    filename = os.path.basename(path)
    m = FILENAME_RE.match(filename)
    if not m:
        return None  # Caller treats this as "skip and report why".

    # The filename is more reliable than the document body for company/period --
    # one report states its period as "Quarter ended March 31, 2025" instead of "Q1 2025".
    company_key = m.group("key")
    quarter = int(m.group("quarter"))
    year = int(m.group("year"))
    canonical_key = COMPANY_KEY_ALIASES.get(company_key, company_key)  # Fold renamed companies together.

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)  # Join all pages into one text blob.

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    display_name = lines[0] if lines else company_key  # First non-blank line is always the company's own header.

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
