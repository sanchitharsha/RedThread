"""
Unit tests for common/urlcheck.py
"""
from unittest.mock import patch
import socket

import pytest
from common.urlcheck import check_url


def _fake_getaddrinfo_public(host, port, family=0, type=0, proto=0, flags=0):
    """Return a fake public IP for any host (simulates DNS resolution)."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def _fake_getaddrinfo_private(host, port, family=0, type=0, proto=0, flags=0):
    """Return a fake private IP (simulates DNS rebinding attack)."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0))]


class TestScheme:
    def test_http_allowed(self):
        check_url("http://example.com/page", ["example.com"])

    def test_https_allowed(self):
        check_url("https://example.com/page", ["example.com"])

    def test_ftp_blocked(self):
        with pytest.raises(ValueError, match="Scheme.*not allowed"):
            check_url("ftp://example.com/file", ["example.com"])

    def test_javascript_blocked(self):
        with pytest.raises(ValueError, match="Scheme.*not allowed"):
            check_url("javascript:alert(1)", ["example.com"])

    def test_file_blocked(self):
        with pytest.raises(ValueError, match="Scheme.*not allowed"):
            check_url("file:///etc/passwd", ["example.com"])


class TestEmptyUrl:
    def test_empty_string(self):
        with pytest.raises(ValueError, match="Empty URL"):
            check_url("", ["example.com"])


class TestHostAllowlist:
    def test_exact_match(self):
        check_url("https://shop.example.com/p", ["shop.example.com"])

    @patch("common.urlcheck.socket.getaddrinfo", side_effect=_fake_getaddrinfo_public)
    def test_subdomain_match(self, mock_dns):
        check_url("https://sub.example.com/p", ["example.com"])

    def test_not_on_list(self):
        with pytest.raises(ValueError, match="not in the allow list"):
            check_url("https://evil.com/page", ["example.com"])

    def test_case_insensitive(self):
        check_url("https://EXAMPLE.COM/page", ["example.com"])

    def test_partial_no_match(self):
        """notexample.com should NOT match example.com (not a subdomain)."""
        with pytest.raises(ValueError, match="not in the allow list"):
            check_url("https://notexample.com/page", ["example.com"])


class TestLocalhost:
    def test_localhost_allowed_when_listed(self):
        check_url("http://localhost:8001/page", ["localhost"])

    def test_localhost_blocked_when_not_listed(self):
        with pytest.raises(ValueError, match="not in the allow list"):
            check_url("http://localhost:8001/page", ["example.com"])

    def test_localhost_with_path(self):
        check_url("http://localhost:8001/product/L01", ["localhost"])


class TestPrivateIP:
    """
    When a non-sandbox subdomain resolves to a private IP, it should be blocked.
    """
    def test_no_host(self):
        with pytest.raises(ValueError):
            check_url("http:///path", ["example.com"])

    @patch("common.urlcheck.socket.getaddrinfo", side_effect=_fake_getaddrinfo_private)
    def test_subdomain_resolves_to_private_ip(self, mock_dns):
        """A subdomain of an allowed domain that resolves to 10.x is blocked."""
        with pytest.raises(ValueError, match="private/reserved IP"):
            check_url("https://evil-sub.example.com/p", ["example.com"])


class TestMultipleDomains:
    @patch("common.urlcheck.socket.getaddrinfo", side_effect=_fake_getaddrinfo_public)
    def test_multiple_domains(self, mock_dns):
        check_url("https://shop.example.com/p", ["other.com", "example.com"])

    def test_none_match(self):
        with pytest.raises(ValueError, match="not in the allow list"):
            check_url("https://evil.com/p", ["a.com", "b.com"])
