import os
from pathlib import Path


def get_local_timezone_name() -> str:
    configured = os.environ.get("CHAT_LOCAL_TIMEZONE")
    if configured:
        return configured

    tz_env = os.environ.get("TZ")
    if tz_env and "/" in tz_env.lstrip(":"):
        return tz_env.lstrip(":")

    localtime = Path("/etc/localtime")
    if localtime.exists():
        resolved = localtime.resolve()
        parts = resolved.parts
        if "zoneinfo" in parts:
            zone_index = parts.index("zoneinfo")
            return "/".join(parts[zone_index + 1 :])

    return "UTC"
