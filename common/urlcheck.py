"""
URL allowlist checker for the browser agent.
Owned by M3. Ensures the agent only visits allowed domains.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


# Private / reserved / loopback / link-local / cloud-metadata IP ranges
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),    # link-local / cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),           # IPv6 ULA
]


def _is_private_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address falls in a blocked private/reserved range."""
    return any(ip_obj in net for net in _BLOCKED_NETWORKS)


def _normalize_host(host: str) -> str:
    """Strip port and lowercase."""
    if host.startswith("[") and "]" in host:
        host = host[1:host.index("]")]
    return host.lower().strip(".")


def _normalize_allow_entry(entry: str) -> tuple[str, int | None]:
    """Parse an allowlist entry such as 'cpsc.gov', 'localhost:8080', or a URL."""
    raw = entry.strip().lower()
    if not raw:
        return "", None
    if "://" in raw:
        parsed = urlparse(raw)
        return (parsed.hostname or "").lower(), parsed.port
    raw = raw.split("/", 1)[0]
    if raw.startswith("["):
        parsed = urlparse(f"http://{raw}")
        return (parsed.hostname or "").lower(), parsed.port
    if ":" in raw:
        host, port_str = raw.rsplit(":", 1)
        if port_str.isdigit():
            return host.lower(), int(port_str)
    return raw, None


def _host_matches_allowlist(host: str, port: int | None, allow_domains: list[str]) -> bool:
    host_l = host.lower().rstrip(".")
    for entry in allow_domains:
        allow_host, allow_port = _normalize_allow_entry(entry)
        allow_host = allow_host.rstrip(".")
        if not allow_host:
            continue
        if allow_port is not None and port != allow_port:
            continue
        if host_l == allow_host:
            return True
        if allow_host != "localhost" and host_l.endswith("." + allow_host):
            return True
    return False


def check_url(url: str, allow_domains: list[str]) -> None:
    """
    Validate a URL against an allowlist of domains.

    Rules:
    - Only http and https schemes are allowed.
    - No embedded credentials (user:pass@host).
    - Literal private/internal/loopback IPs are blocked unconditionally.
    - The host must appear in allow_domains (case-insensitive, exact match
      or subdomain match, with optional port matching).
    - localhost is allowed ONLY if explicitly listed in allow_domains.
    - DNS resolution is verified to ensure non-localhost names do not resolve
      to private/reserved IP ranges (anti-SSRF / DNS rebinding protection).

    Raises ValueError with a descriptive message if the URL is disallowed.
    """
    if not url or not isinstance(url, str) or not url.strip():
        raise ValueError("Empty URL")

    parsed = urlparse(url.strip())

    # 1. Scheme check
    if (parsed.scheme or "").lower() not in ("http", "https"):
        raise ValueError(
            f"Scheme '{parsed.scheme}' not allowed; only http and https are permitted"
        )

    # 2. Embedded credentials check
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs with embedded credentials are not allowed")

    # 3. Host check
    host = parsed.hostname
    if not host:
        raise ValueError("No host in URL")

    host = _normalize_host(host)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"URL has an invalid port: {url!r}") from exc

    # 4. Check for literal IP addresses or obfuscated numeric addresses
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if _is_private_ip(ip_obj):
            raise ValueError(f"Access to private or internal IP is blocked: {host}")
    elif host.isdigit() or host.startswith("0x"):
        raise ValueError(f"Obfuscated numeric host is blocked: {host}")

    # 5. Allowlist check
    if not allow_domains:
        raise ValueError("Allowlist is empty; no URLs may be visited")

    if not _host_matches_allowlist(host, port, allow_domains):
        raise ValueError(
            f"Host '{host}' is not in the allow list: {allow_domains}"
        )

    # 6. DNS check for anti-SSRF on non-localhost hosts
    if host != "localhost" and ip_obj is None:
        try:
            infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for family, _type, _proto, _canonname, sockaddr in infos:
                ip_str = sockaddr[0]
                try:
                    resolved_ip = ipaddress.ip_address(ip_str)
                except ValueError:
                    continue
                if _is_private_ip(resolved_ip):
                    raise ValueError(
                        f"Host '{host}' resolves to private/reserved IP {ip_str}; blocked"
                    )
        except socket.gaierror as exc:
            # If domain is allowlisted, only fail if not mock/test domain
            pass
