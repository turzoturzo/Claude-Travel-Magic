"""Multi-format date parsing for travel emails."""

import re
from datetime import date, datetime
from typing import Optional

from dateutil import parser as dateutil_parser


def parse_date(raw: str) -> Optional[date]:
    """Parse a date string in many formats, returning a date or None.

    Handles:
      - YYYY-MM-DD
      - DD Mon YYYY / Mon DD, YYYY
      - MM/DD/YYYY
      - DDMONYYYY (e.g. 20JAN22, 09MAR2022)
      - RFC 2822 email dates
      - "Tue, Feb 20" style (no year — returns None since we can't guess)
    """
    if not raw or raw.strip().lower() in ("null", "none", "not specified", "unknown", ""):
        return None

    raw = raw.strip()

    # 1. DDMONYY / DDMONYYYY (e.g. 20JAN22, 09MAR2022)
    m = re.match(r'^(\d{2})([A-Z]{3})(\d{2,4})$', raw, re.I)
    if m:
        day, mon, year = m.groups()
        year = year if len(year) == 4 else f"20{year}"
        try:
            return datetime.strptime(f"{day}{mon.upper()}{year}", "%d%b%Y").date()
        except ValueError:
            pass

    # 2. YYYY-MM-DD
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', raw)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # 3. MM/DD/YYYY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', raw)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # 4. dateutil as general fallback (handles RFC 2822, "26 March 2024", etc.)
    try:
        dt = dateutil_parser.parse(raw, fuzzy=True)
        return dt.date()
    except (ValueError, OverflowError):
        pass

    return None


def parse_date_with_context(raw: str, email_date_str: str = "") -> Optional[date]:
    """Parse a date, using the email's send date to fill in missing year."""
    result = parse_date(raw)
    if result:
        return result

    # If raw is like "Feb 20" or "March 25" with no year, try adding the email year
    if email_date_str:
        email_date = parse_date(email_date_str)
        if email_date:
            try:
                dt = dateutil_parser.parse(raw, default=datetime(email_date.year, 1, 1), fuzzy=True)
                return dt.date()
            except (ValueError, OverflowError):
                pass

    return None
