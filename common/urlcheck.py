"""
URL allowlist checker for the browser agent.
Owned by M3. Ensures the agent only visits allowed domains.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


# Private / reserved IP ranges that are blocked by default
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),    # link-local
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),           # IPv6 ULA
    # Cloud metadata endpoints
    ipaddress.ip_network("169.254.169.254/32"),
]


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address falls in a blocked private/reserved range."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for net in _BLOCKED_NETWORKS:
        if addr in net:
            return True
    return False


def _normalize_host(host: str) -> str:
    """Strip port and lowercase."""
    # Remove brackets from IPv6
    if host.startswith("[") and "]" in host:
        host = host[1:host.index("]")]
    return host.lower().strip(".")


def check_url(url: str, allow_domains: list[str]) -> None:
    """
    Validate a URL against an allowlist of domains.

    Rules:
    - Only http and https schemes are allowed.
    - The host must appear in allow_domains (case-insensitive, exact match
      or subdomain match).
    - If the host is NOT explicitly in the allowlist, DNS resolution is
      performed and the resolved IP must not be in a private/reserved/
      link-local/cloud-metadata range.
    - localhost is allowed ONLY if explicitly listed in allow_domains.

    Raises ValueError with a descriptive message if the URL is disallowed.
    """
    if not url:
        raise ValueError("Empty URL")

    parsed = urlparse(url)

    # 1. Scheme check
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Scheme '{parsed.scheme}' not allowed; only http and https are permitted"
        )

    # 2. Host check
    host = parsed.hostname
    if not host:
        raise ValueError("No host in URL")

    host = _normalize_host(host)

    # Normalize allow_domains
    allowed = [d.lower().strip(".") for d in allow_domains]

    # Check if host is on the allowlist (exact or subdomain)
    host_allowed = False
    for domain in allowed:
        if host == domain or host.endswith("." + domain):
            host_allowed = True
            break

    if not host_allowed:
        raise ValueError(
            f"Host '{host}' is not in the allow list: {allow_domains}"
        )

    # 3. DNS resolution check for SSRF protection
    # Skip DNS check for:
    #   - Sandbox hosts (localhost, 127.0.0.1, ::1) that intentionally
    #     resolve to loopback
    #   - Hosts that are an exact match in the allowlist (the admin
    #     explicitly trusts them; DNS may not resolve in dev/CI)
    # Resolve only when the host matched via subdomain wildcard to catch
    # DNS rebinding attacks pointing a subdomain at a private IP.
    _SANDBOX_HOSTS = {"localhost", "127.0.0.1", "::1"}
    is_sandbox_host = host in _SANDBOX_HOSTS
    is_exact_allowed = host in allowed  # exact match, not just subdomain

    needs_dns_check = not is_sandbox_host and not is_exact_allowed

    if needs_dns_check:
        try:
            infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(f"DNS resolution failed for '{host}': {exc}") from exc

        for family, _type, _proto, _canonname, sockaddr in infos:
            ip_str = sockaddr[0]
            if _is_private_ip(ip_str):
                raise ValueError(
                    f"Host '{host}' resolves to private/reserved IP {ip_str}; blocked"
                )
