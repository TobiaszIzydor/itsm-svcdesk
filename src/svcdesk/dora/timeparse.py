# ai-generated: 85% - Claude Code wrote the code from my design (module layout, algorithms, rounding and validation rules given in the prompt)
"""RFC 3339 instants: strict parsing (an offset is required) and UTC formatting."""

import re
from datetime import datetime, timedelta, timezone

# Full date-time with a mandatory offset. [0-9] rather than \d: \d also matches non-ASCII digits.
RFC3339 = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]+)?([Zz]|[+-][0-9]{2}:[0-9]{2})"
)


def parse_instant(s: object) -> datetime:
    """An RFC 3339 instant with an offset, as an aware UTC datetime; anything else raises ValueError.

    Fractional seconds beyond microseconds are truncated (datetime's resolution).
    """
    if not isinstance(s, str):
        raise ValueError("not a string")
    m = RFC3339.fullmatch(s)
    if m is None:
        raise ValueError("not an RFC 3339 instant with an offset")
    year, month, day, hour, minute, second = (int(g) for g in m.groups()[:6])
    fraction = m.group(7)
    micros = int((fraction[1:] + "000000")[:6]) if fraction else 0
    offset = m.group(8)
    if offset in ("Z", "z"):
        tz = timezone.utc
    else:
        oh, om = int(offset[1:3]), int(offset[4:6])
        if oh > 23 or om > 59:
            raise ValueError("offset out of range")
        delta = timedelta(hours=oh, minutes=om)
        tz = timezone(-delta if offset[0] == "-" else delta)
    try:
        return datetime(year, month, day, hour, minute, second, micros, tzinfo=tz).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError(str(exc)) from None


def format_instant(dt: datetime) -> str:
    """UTC with a Z suffix; fractional seconds only when present."""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
