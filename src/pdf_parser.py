"""Reads one PDF report and turns it into a structured record.

This is where PDF text (via pdfplumber), the metric alias table (config.py),
and the value-token parsing (values.py) all come together.
"""
import os
import re

import pdfplumber

from config import FILENAME_RE, COMPANY_KEY_ALIASES, METRIC_ALIASES, HEADCOUNT_NARRATIVE_PATTERNS
from values import parse_value, extract_value_after_label


def nonblank_lines(text):
    """Split `text` into stripped, non-empty lines."""
    return [l.strip() for l in text.splitlines() if l.strip()]


def _metric_entry(raw_label, raw_value):
    """Build one extracted-metric record, keeping the raw source text for auditability."""
    value, unit = parse_value(raw_value)
    return {
        "raw_label": raw_label,   # The exact source line the value came from.
        "raw_value": raw_value,   # The exact source token, before parsing.
        "value": value,
        "unit": unit,
    }


def _find_labelled_value(lines, aliases):
    """Return the first (line, token) hit for these aliases, trying the most specific first."""
    for alias in aliases:
        for line in lines:
            token = extract_value_after_label(line, alias)
            if token:
                return line, token
    return None, None


def extract_metrics_from_text(text):
    """Scan `text` for each canonical metric in METRIC_ALIASES, returning whatever it finds."""
    lines = nonblank_lines(text)
    metrics = {}

    for canonical, aliases in METRIC_ALIASES.items():
        # Stop at the first hit -- we only want one value per metric per document.
        found_line, found_token = _find_labelled_value(lines, aliases)
        if found_token:
            metrics[canonical] = _metric_entry(found_line, found_token)

    # Headcount is sometimes only mentioned in a sentence, not a table row.
    # Only fall back to narrative text if the table-based pass above found nothing.
    if "headcount" not in metrics:
        for pattern in HEADCOUNT_NARRATIVE_PATTERNS:
            m = pattern.search(text)
            if m:
                metrics["headcount"] = _metric_entry("(from narrative text, not a table row)", m.group(1))
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

    lines = nonblank_lines(text)
    display_name = lines[0] if lines else company_key  # First non-blank line is always the company's own header.

    return {
        "file": filename,
        "company_key": canonical_key,
        "company_display_name": display_name,
        "quarter": quarter,
        "year": year,
        "reporting_currency": detect_currency(text),
        "metrics": extract_metrics_from_text(text),
    }
