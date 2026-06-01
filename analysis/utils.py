import re
from datetime import datetime
from typing import Optional


def parse_date_ymd(date_str: str) -> Optional[str]:
    """Return YYYY-MM-DD from either an ISO-short or verbose git date string."""
    if not date_str:
        return None
    s = str(date_str).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %Y %z").strftime("%Y-%m-%d")
    except ValueError:
        pass
    return None
