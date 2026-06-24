from datetime import datetime

from django.conf import settings
from strands import tool
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from chat.tools.timezone import get_local_timezone_name


@tool
def current_time(timezone: str | None = None) -> str:
    """Get the current time in ISO 8601 format.

    Uses the server's local timezone by default. For example, a machine in
    Japan returns Asia/Tokyo (UTC+9).

    Args:
        timezone: Optional IANA timezone override (for example, "Asia/Tokyo").

    Returns:
        The current time in ISO 8601 format, including the timezone offset.
    """
    tz_name = timezone or getattr(settings, "CHAT_LOCAL_TIMEZONE", None) or get_local_timezone_name()
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid timezone: {tz_name}") from exc

    return datetime.now(tz).isoformat()
