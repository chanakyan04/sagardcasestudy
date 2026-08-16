"""Constants and patterns shared across the extraction pipeline.

Nothing in this file does any work by itself — it's just the configuration
that pdf_parser.py and values.py read from. Keeping it separate means the
"what metrics do we look for, and under what names" question lives in one
place, away from the parsing logic that acts on it.
"""
import re

# Matches filenames like "ApexFreight_Q2_2025.pdf" and pulls out the company
# key, quarter number, and year as named groups.
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

# A "value-shaped" token: optional leading '(' and '$', a number (with optional
# commas/decimal), an optional unit suffix (%, bps, M, K, x), optional trailing ')'.
# Matches things like "$12.7M", "(0.55M)", "148bps", "96.1%", "2.4x", "1,042".
VALUE_TOKEN_RE = re.compile(
    r"^\(?-?\$?\d[\d,]*(?:\.\d+)?(?:%|bps|M|K|x)?\)?$", re.IGNORECASE
)

# Canonical metric -> ordered list of label phrasings (most specific first).
# A line is treated as a match if it starts with one of these phrases
# (case-insensitive) and a numeric token follows somewhere on the line.
# Order matters: e.g. "total recognized revenue" is checked before the plainer
# "recognized revenue" so a subtotal line doesn't win over the real total.
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
# table row (e.g. "the team ended the quarter at 199 employees"). These
# patterns are tried, in order, only when the table-based match above fails.
HEADCOUNT_NARRATIVE_PATTERNS = [
    re.compile(r"ended (?:the quarter|the period) (?:at|with) (\d[\d,]*)\s+employees", re.IGNORECASE),
    re.compile(r"headcount of (\d[\d,]*)\b", re.IGNORECASE),
]
