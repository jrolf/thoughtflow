"""
Internal cron expression parser for CHRON.

Supports standard 5-field cron expressions:

    minute  hour  day-of-month  month  day-of-week

Field syntax:
    *        any value
    5        exact value
    1-5      range (inclusive)
    */15     step from start of range
    1-5/2    range with step
    1,3,5    comma-separated list of values or sub-expressions

Day-of-week uses cron convention: 0 = Sunday, 6 = Saturday.
Both 0 and 7 are accepted as Sunday.

This module has no dependencies beyond the standard library.
"""

from __future__ import annotations

from datetime import timedelta


# Valid ranges for each of the five cron fields
FIELD_RANGES = [
    (0, 59),   # minute
    (0, 23),   # hour
    (1, 31),   # day of month
    (1, 12),   # month
    (0, 6),    # day of week (0=Sunday, 6=Saturday)
]

FIELD_NAMES = ["minute", "hour", "day", "month", "weekday"]


def parse_field(token, min_val, max_val):
    """
    Parse a single cron field token into a set of allowed integer values.

    Handles wildcards, exact values, ranges, steps, and comma-separated
    lists of any combination of these.

    Args:
        token: Field string (e.g. "*/15", "1-5", "3,7,11").
        min_val: Minimum valid value for this field.
        max_val: Maximum valid value for this field.

    Returns:
        frozenset of int: Allowed values for this field.

    Raises:
        ValueError: If the token cannot be parsed or contains out-of-range values.

    Example:
        >>> parse_field("*/15", 0, 59)
        frozenset({0, 15, 30, 45})
        >>> parse_field("1-5", 0, 6)
        frozenset({1, 2, 3, 4, 5})
    """
    result = set()

    for part in token.split(","):
        part = part.strip()

        if "/" in part:
            range_part, step_str = part.split("/", 1)
            step = int(step_str)
            if step <= 0:
                raise ValueError("Step must be positive, got {}".format(step))

            if range_part == "*":
                start, end = min_val, max_val
            elif "-" in range_part:
                start, end = _parse_range(range_part)
            else:
                start = int(range_part)
                end = max_val

            for v in range(start, end + 1, step):
                if min_val <= v <= max_val:
                    result.add(v)

        elif part == "*":
            result.update(range(min_val, max_val + 1))

        elif "-" in part:
            start, end = _parse_range(part)
            for v in range(start, end + 1):
                if min_val <= v <= max_val:
                    result.add(v)

        else:
            v = int(part)
            if min_val <= v <= max_val:
                result.add(v)
            elif v == 7 and max_val == 6:
                # Special case: 7 is accepted as Sunday (same as 0)
                result.add(0)
            else:
                raise ValueError(
                    "Value {} out of range {}-{}".format(v, min_val, max_val)
                )

    if not result:
        raise ValueError("Empty result for cron field: '{}'".format(token))

    return frozenset(result)


def _parse_range(token):
    """
    Parse a "start-end" range token into two integers.

    Args:
        token: Range string like "1-5".

    Returns:
        tuple: (start, end) as integers.
    """
    parts = token.split("-", 1)
    return int(parts[0]), int(parts[1])


def parse_cron(expression):
    """
    Parse a 5-field cron expression into a dict of allowed value sets.

    Standard cron has a special rule for the day fields: when both
    day-of-month and day-of-week are explicitly restricted (not ``*``),
    a date matches if EITHER field is satisfied (OR logic). When only
    one is restricted, only that field must match.

    This function records whether each day field was restricted so that
    matching can apply the correct logic.

    Args:
        expression: Cron string like "0 9 * * 1-5".

    Returns:
        dict: Keys are ``minute``, ``hour``, ``day``, ``month``,
            ``weekday`` (each a frozenset of ints), plus
            ``day_restricted`` and ``weekday_restricted`` (bools).

    Raises:
        ValueError: If the expression does not have exactly 5 fields
            or any field is malformed.

    Example:
        >>> fields = parse_cron("0 9 * * 1-5")
        >>> 0 in fields["minute"]
        True
        >>> 9 in fields["hour"]
        True
        >>> fields["weekday_restricted"]
        True
    """
    tokens = expression.strip().split()
    if len(tokens) != 5:
        raise ValueError(
            "Cron expression must have 5 fields "
            "(minute hour day month weekday), got {}: '{}'"
            .format(len(tokens), expression)
        )

    fields = {}
    for i, (name, (lo, hi)) in enumerate(zip(FIELD_NAMES, FIELD_RANGES)):
        fields[name] = parse_field(tokens[i], lo, hi)

    # Track whether day-of-month / day-of-week are explicitly restricted
    fields["day_restricted"] = tokens[2] != "*"
    fields["weekday_restricted"] = tokens[4] != "*"

    return fields


def _to_cron_weekday(python_weekday):
    """
    Convert Python weekday (0=Monday, 6=Sunday) to cron weekday (0=Sunday, 6=Saturday).

    Args:
        python_weekday: int from datetime.weekday().

    Returns:
        int: Cron-convention weekday.
    """
    return (python_weekday + 1) % 7


def cron_matches(fields, dt):
    """
    Check whether a datetime matches a parsed cron expression.

    Applies the standard cron OR-logic for day fields when both
    day-of-month and day-of-week are restricted.

    Args:
        fields: Parsed cron dict from parse_cron().
        dt: datetime to check (only minute, hour, day, month, weekday are examined).

    Returns:
        bool: True if dt satisfies all cron fields.

    Example:
        >>> fields = parse_cron("30 9 * * 1-5")
        >>> from datetime import datetime
        >>> # Monday at 9:30
        >>> cron_matches(fields, datetime(2026, 3, 16, 9, 30))
        True
    """
    if dt.minute not in fields["minute"]:
        return False
    if dt.hour not in fields["hour"]:
        return False
    if dt.month not in fields["month"]:
        return False

    cron_dow = _to_cron_weekday(dt.weekday())
    day_ok = dt.day in fields["day"]
    weekday_ok = cron_dow in fields["weekday"]

    both_restricted = fields["day_restricted"] and fields["weekday_restricted"]

    if both_restricted:
        # Standard cron: match if EITHER condition is met
        if not (day_ok or weekday_ok):
            return False
    else:
        if not day_ok:
            return False
        if not weekday_ok:
            return False

    return True


def next_cron_match(fields, after):
    """
    Find the next datetime after ``after`` that matches the cron expression.

    Uses skip-ahead logic (jumps over non-matching months, days, and hours)
    so it does not iterate minute-by-minute across long gaps.

    Searches up to approximately 4 years ahead. Returns None if no match
    is found within that window.

    Args:
        fields: Parsed cron dict from parse_cron().
        after: Naive datetime to search from (exclusive). The returned
            datetime will be strictly after this value.

    Returns:
        datetime or None: Next matching datetime, or None if no match
            exists within the search window.

    Example:
        >>> fields = parse_cron("0 9 * * *")
        >>> after = datetime(2026, 3, 13, 10, 0)
        >>> next_cron_match(fields, after)
        datetime.datetime(2026, 3, 14, 9, 0)
    """
    # Start one minute after `after`, floored to the minute
    dt = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Search limit: ~4 years
    limit = after + timedelta(days=366 * 4)

    while dt <= limit:
        # Skip months that don't match
        if dt.month not in fields["month"]:
            dt = _advance_to_next_month(dt, fields["month"])
            if dt is None or dt > limit:
                return None
            continue

        # Skip days that don't match
        cron_dow = _to_cron_weekday(dt.weekday())
        both_restricted = fields["day_restricted"] and fields["weekday_restricted"]

        if both_restricted:
            day_ok = (dt.day in fields["day"]) or (cron_dow in fields["weekday"])
        else:
            day_ok = (dt.day in fields["day"]) and (cron_dow in fields["weekday"])

        if not day_ok:
            dt = (dt + timedelta(days=1)).replace(hour=0, minute=0)
            continue

        # Skip hours that don't match
        if dt.hour not in fields["hour"]:
            dt = dt.replace(minute=0) + timedelta(hours=1)
            continue

        # Check minute
        if dt.minute in fields["minute"]:
            return dt

        # Advance to next minute
        dt += timedelta(minutes=1)

    return None


def _advance_to_next_month(dt, valid_months):
    """
    Advance dt to the 1st of the next month that appears in valid_months.

    Resets the time to 00:00. Tries up to 48 months ahead (4 years)
    before giving up and returning None.

    Args:
        dt: Current datetime.
        valid_months: frozenset of valid month numbers (1-12).

    Returns:
        datetime or None.
    """
    year = dt.year
    month = dt.month

    for _ in range(48):
        month += 1
        if month > 12:
            month = 1
            year += 1

        if month in valid_months:
            return dt.replace(year=year, month=month, day=1, hour=0, minute=0)

    return None
