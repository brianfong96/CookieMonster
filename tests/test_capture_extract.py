"""Tests for cookie_monster.capture extract helpers.

Covers audience_domain(), extract_tokens(), and extract_token_details().
"""

from __future__ import annotations

from cookie_monster.capture import audience_domain, extract_token_details, extract_tokens

# ── audience_domain ───────────────────────────────────────────────────────────


def test_audience_domain_extracts_netloc():
    assert audience_domain("https://api.github.com/graphql") == "api.github.com"
    assert audience_domain("http://localhost:8080/api") == "localhost:8080"


def test_audience_domain_handles_bare_string():
    assert audience_domain("not-a-url") == "not-a-url"


def test_audience_domain_handles_empty():
    result = audience_domain("")
    assert isinstance(result, str)


# ── extract_tokens ────────────────────────────────────────────────────────────


def test_extract_tokens_finds_matching_headers():
    captures = [
        {"headers": {"X-Request-Id": "abc"}},
        {"headers": {"Cookie": "session=xyz", "Authorization": "Bearer tok123"}},
        {"headers": {"Cookie": "ignored"}},
    ]
    tokens = extract_tokens(captures, ["cookie", "authorization"])
    assert tokens["cookie"] == "session=xyz"
    assert tokens["authorization"] == "Bearer tok123"


def test_extract_tokens_returns_none_for_missing():
    captures = [{"headers": {"Cookie": "a=1"}}]
    tokens = extract_tokens(captures, ["cookie", "authorization", "x-csrf-token"])
    assert tokens["cookie"] == "a=1"
    assert tokens["authorization"] is None
    assert tokens["x-csrf-token"] is None


def test_extract_tokens_case_insensitive():
    captures = [{"headers": {"COOKIE": "upper=1", "authorization": "lower"}}]
    tokens = extract_tokens(captures, ["Cookie", "Authorization"])
    assert tokens["cookie"] == "upper=1"
    assert tokens["authorization"] == "lower"


def test_extract_tokens_empty_captures():
    tokens = extract_tokens([], ["cookie"])
    assert tokens == {"cookie": None}


# ── extract_token_details ────────────────────────────────────────────────────


def test_extract_token_details_multiple_requests():
    """Headers from different requests should each produce a detail entry."""
    captures = [
        {
            "url": "https://github.com/",
            "method": "GET",
            "headers": {"Cookie": "session=abc", "Authorization": "Bearer tok1"},
        },
        {
            "url": "https://api.github.com/graphql",
            "method": "POST",
            "headers": {"Cookie": "session=abc", "Authorization": "Bearer tok2"},
        },
    ]
    details = extract_token_details(captures, ["cookie", "authorization"])
    assert len(details) >= 3  # at least 3 unique (header, value, domain)

    domains = {d["audience_domain"] for d in details}
    assert "github.com" in domains
    assert "api.github.com" in domains

    for d in details:
        assert "header" in d
        assert "value" in d
        assert "audience_url" in d
        assert "audience_domain" in d
        assert "method" in d


def test_extract_token_details_deduplicates_same_value_same_domain():
    """Same header+value+domain should be collapsed to one entry."""
    captures = [
        {
            "url": "https://github.com/page1",
            "method": "GET",
            "headers": {"Cookie": "session=abc"},
        },
        {
            "url": "https://github.com/page2",
            "method": "GET",
            "headers": {"Cookie": "session=abc"},
        },
    ]
    details = extract_token_details(captures, ["cookie"])
    cookie_details = [d for d in details if d["header"] == "cookie"]
    assert len(cookie_details) == 1
    assert cookie_details[0]["audience_domain"] == "github.com"


def test_extract_token_details_different_values_same_domain():
    captures = [
        {
            "url": "https://api.example.com/a",
            "method": "GET",
            "headers": {"Authorization": "Bearer token-A"},
        },
        {
            "url": "https://api.example.com/b",
            "method": "POST",
            "headers": {"Authorization": "Bearer token-B"},
        },
    ]
    details = extract_token_details(captures, ["authorization"])
    assert len(details) == 2
    values = {d["value"] for d in details}
    assert "Bearer token-A" in values
    assert "Bearer token-B" in values


def test_extract_token_details_empty_captures():
    details = extract_token_details([], ["cookie"])
    assert details == []


def test_extract_token_details_ignores_non_requested_headers():
    captures = [
        {
            "url": "https://example.com/",
            "method": "GET",
            "headers": {"Cookie": "a=1", "X-Request-Id": "abc123"},
        },
    ]
    details = extract_token_details(captures, ["cookie"])
    assert len(details) == 1
    assert details[0]["header"] == "cookie"


def test_extract_token_details_case_insensitive():
    captures = [
        {
            "url": "https://example.com/",
            "method": "GET",
            "headers": {"AUTHORIZATION": "Bearer UP", "cookie": "low=1"},
        },
    ]
    details = extract_token_details(captures, ["Cookie", "Authorization"])
    headers = {d["header"] for d in details}
    assert "cookie" in headers
    assert "authorization" in headers


def test_extract_token_details_preserves_method():
    captures = [
        {
            "url": "https://api.example.com/data",
            "method": "POST",
            "headers": {"Authorization": "Bearer x"},
        },
    ]
    details = extract_token_details(captures, ["authorization"])
    assert details[0]["method"] == "POST"
