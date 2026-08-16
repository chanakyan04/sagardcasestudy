"""Low-level helpers for turning a raw text token into a numeric value.

These functions don't know anything about PDFs or metrics -- they just deal
with strings like "$12.7M" or "(0.55M)" and turn them into numbers, or scan
a line of text for the first one.
"""
from config import VALUE_TOKEN_RE


def parse_value(raw):
    """Parse a raw value token like '$12.7M', '($0.55M)', '148bps', '96.1%' into (numeric, unit)."""
    if raw is None:
        return None, None

    token = raw.strip()

    # Parenthesized numbers are the standard accounting convention for negatives, e.g. "(0.55M)" means -0.55M.
    negative = token.startswith("(") and token.endswith(")")
    token = token.strip("()")  # Drop the parens now that we've recorded whether they were there.

    # Some values use a leading minus sign instead of parens; handle both.
    if token.startswith("-"):
        negative = True
        token = token[1:]

    token = token.replace("$", "").replace(",", "")  # Strip currency symbol and thousands separators.

    # Pull off a trailing unit suffix, if present, so what's left is a plain float string.
    unit = None
    for suffix in ("bps", "%", "M", "K", "x"):
        if token.lower().endswith(suffix.lower()):
            unit = suffix
            token = token[: -len(suffix)]
            break

    try:
        num = float(token)
    except ValueError:
        return None, None  # Whatever was left over isn't actually numeric -- not a real value.

    if negative:
        num = -num

    return num, unit


def extract_value_after_label(line, alias):
    """If `line` starts with `alias`, return the first numeric-looking token found after it, else None."""
    lower = line.lower()
    if not lower.startswith(alias):
        return None  # This line isn't a match for this label at all.

    remainder = line[len(alias):].strip()  # Everything on the line after the label text.

    # Scan word-by-word rather than assuming the value is immediately next --
    # some labels have trailing annotations (e.g. "Net Pound Retention – NPR (LTM) 117%")
    # before the actual number.
    for tok in remainder.split():
        if VALUE_TOKEN_RE.match(tok):
            return tok

    return None  # Label matched, but nothing on the rest of the line looked like a value.
