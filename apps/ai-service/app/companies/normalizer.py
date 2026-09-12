from __future__ import annotations

import re
from urllib.parse import urlparse


def normalize_domain(url_or_domain: str | None) -> str | None:
    if not url_or_domain:
        return None
    value = url_or_domain.strip().lower()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    host = parsed.hostname
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host


def normalize_company_name(name: str, strip_stopwords: bool = False) -> str:
    cleaned = name.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for suffix in (" inc", " llc", " ltd", " corp", " co", " gmbh", " plc"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    if strip_stopwords:
        from app.utils.stopwords import remove_stopwords
        without_stops = remove_stopwords(cleaned)
        if without_stops:
            cleaned = without_stops
    return cleaned
