import re
from datetime import datetime

def normalize_string(val):
    """Collapse multiple spaces and convert to uppercase trimmed string."""
    if not val:
        return ""
    # Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', str(val).strip())
    return cleaned

def parse_datetime_safe(date_str):
    """
    Safely parse HIS datetime strings into standard (YYYY-MM-DD, HH:MM).
    Formats handled:
    - 04.09.2026 15:50
    - 06.09.2026 1:20
    - 06.09.2026 7:26
    - 2026-09-04 15:50:00
    - 04/09/2026 15:50
    - 2026-09-04
    """
    if not date_str or not str(date_str).strip():
        return None, None

    date_str = str(date_str).strip()

    formats = [
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d/%m/%Y"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
        except ValueError:
            continue

    return None, None
