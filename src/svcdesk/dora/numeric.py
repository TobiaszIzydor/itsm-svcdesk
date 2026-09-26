# ai-generated: 85% - Claude Code wrote the code from my design (module layout, algorithms, rounding and validation rules given in the prompt)
"""Exact Decimal arithmetic (R-03, R-04). Rounding happens once, at output, half-up - never round()."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

ZERO = Decimal(0)
WHOLE = Decimal("1")
SIX_PLACES = Decimal("0.000001")
PRECISION = 60  # far beyond any value here, so division and quantize never lose a digit that matters


def seconds_between(a: datetime, b: datetime) -> Decimal:
    """b - a in seconds, exactly (microsecond resolution)."""
    d = b - a
    return Decimal(d.days) * 86400 + Decimal(d.seconds) + Decimal(d.microseconds).scaleb(-6)


def clamp0(x: Decimal) -> Decimal:
    return x if x > ZERO else ZERO


def divide(numerator: Decimal | int, denominator: Decimal | int) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return Decimal(numerator) / Decimal(denominator)


def median(values: list[Decimal]) -> Decimal | None:
    """Middle value; mean of the two middle values for an even count; None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return (ordered[mid - 1] + ordered[mid]) / 2


def round_seconds(x: Decimal | None) -> int | None:
    if x is None:
        return None
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return int(x.quantize(WHOLE, rounding=ROUND_HALF_UP))


def round_ratio(x: Decimal | None) -> float | None:
    if x is None:
        return None
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return float(x.quantize(SIX_PLACES, rounding=ROUND_HALF_UP))
