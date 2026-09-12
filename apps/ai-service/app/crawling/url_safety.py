from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

LOCALHOST_HOSTS = {"localhost", "0.0.0.0", "::1"}


class UnsafeURLError(ValueError):
    pass


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURLError("Only HTTP/HTTPS URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeURLError("URL must include a hostname")
    if host in LOCALHOST_HOSTS or host.endswith(".localhost"):
        raise UnsafeURLError("Localhost URLs are blocked")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        for network in PRIVATE_NETWORKS:
            if ip in network:
                raise UnsafeURLError("Private IP ranges are blocked")
    if re.search(r"(^|\.)local$", host):
        raise UnsafeURLError("Local network hostnames are blocked")
    return url
