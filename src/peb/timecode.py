"""Convert between seconds and h:mm:ss timecodes."""


def format_hms(seconds: float) -> str:
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def parse_hms(text: str) -> float:
    """Parse m:ss, h:mm:ss or VTT hh:mm:ss.mmm into seconds."""
    parts = text.strip().split(":")
    if not 2 <= len(parts) <= 3:
        raise ValueError(f"bad timecode: {text!r}")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds
