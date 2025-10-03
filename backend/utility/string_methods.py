import re
from pathlib import Path


def clean_allow(name: str) -> str:
    """Replace all unexpected characters with underscores"""
    name = name.strip().lower()
    # replace any non-alphanumeric, dash, or underscore with underscore
    cleaned = re.sub(r"[^a-z0-9_-]+", "_", name)
    # trim leading/trailing underscores
    return cleaned.strip("_")


def sanitize_filename(name: str) -> str:
    """Sanitize a filename while preserving a safe extension when present."""

    candidate = Path(name).name
    if not candidate:
        return "file"

    if "." in candidate:
        stem, ext = candidate.rsplit(".", 1)
        sanitized_stem = clean_allow(stem)
        sanitized_ext = re.sub(r"[^a-z0-9]+", "", ext.lower())
        if sanitized_stem and sanitized_ext:
            return f"{sanitized_stem}.{sanitized_ext}"
        if sanitized_stem:
            return sanitized_stem

    sanitized = clean_allow(candidate)
    return sanitized or "file"
