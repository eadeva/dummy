"""Pure projections of one captured, timezone-aware invocation timestamp."""

from datetime import UTC, datetime

DATE_FORMATS = {
    "timestamp": "%Y_%m_%d_%H%M",
    "timestamp_seconds": "%Y_%m_%d_%H%M%S",
    "year": "%Y",
    "month": "%m",
    "day": "%d",
    "hour": "%H",
    "minute": "%M",
    "second": "%S",
    "offset": "%z",
}
DATE_FIELDS = {*DATE_FORMATS, "iso"}


def date_values(instant: datetime) -> dict:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("date substitutions require a timezone-aware timestamp")

    def project(value):
        return {
            **{name: value.strftime(fmt) for name, fmt in DATE_FORMATS.items()},
            "iso": value.isoformat(timespec="seconds"),
        }

    return {**project(instant), "utc": project(instant.astimezone(UTC))}


def valid_date_field(path: str) -> bool:
    return path in DATE_FIELDS or (path.startswith("utc.") and path[4:] in DATE_FIELDS)
