import re


def clean_allow(name: str) -> str:
    """Replace all unexpected characters with underscores"""
    name = name.strip().lower()
    # replace any non-alphanumeric, dash, or underscore with underscore
    cleaned = re.sub(r"[^a-z0-9_-]+", "_", name)
    # trim leading/trailing underscores
    return cleaned.strip("_")
