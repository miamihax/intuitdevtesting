def parse_hhmm(value: str) -> int:
    """Parse "HH:MM" into minutes since midnight."""
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def format_minutes(total_minutes: float) -> str:
    """Format minutes-since-midnight as "HH:MM", wrapping past 24h."""
    wrapped = round(total_minutes) % (24 * 60)
    hours, minutes = divmod(wrapped, 60)
    return f"{hours:02d}:{minutes:02d}"
