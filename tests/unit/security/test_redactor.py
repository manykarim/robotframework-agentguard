"""Tests for `AgentGuard.security.redactor` — secret + PII redaction."""

from __future__ import annotations

import pytest

from AgentGuard.security.redactor import (
    find_secrets,
    redact,
    redact_dict,
    serialize_trajectory,
)


class TestRedactStrict:
    @pytest.mark.parametrize(
        "text,kind",
        [
            ("token: sk-ant-1234567890abcdefghij", "ANTHROPIC_KEY"),
            ("Authorization: Bearer ABCDEFGHIJ012345", "BEARER_TOKEN"),
            ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payloadabcabc.signaturexyzxyzx", "JWT"),
            ("AKIAABCDEFGHIJ012345", "AWS_ACCESS_KEY"),
            ("ghp_" + "a" * 36, "GITHUB_PAT"),
            ("xoxb-1234567890-abcdefg", "SLACK_TOKEN"),
        ],
    )
    def test_strict_mode_replaces_with_redacted_kind(self, text: str, kind: str) -> None:
        out = redact(text, mode="strict")
        assert f"<REDACTED:{kind}>" in out

    def test_email_redacted(self) -> None:
        out = redact("Contact alice@example.com for info", mode="strict")
        assert "<REDACTED:EMAIL>" in out

    def test_pem_block_detected(self) -> None:
        out = redact("-----BEGIN RSA PRIVATE KEY-----", mode="strict")
        assert "<REDACTED:PEM_BLOCK>" in out


class TestTokenizeMode:
    def test_consistent_hashes(self) -> None:
        secret = "sk-ant-abcdefghijklmnopqrst"
        out1 = redact(f"a {secret}", mode="tokenize")
        out2 = redact(f"b {secret}", mode="tokenize")
        # Same secret produces same 8-char hash.
        token1 = out1.split("a ")[1]
        token2 = out2.split("b ")[1]
        assert token1 == token2

    def test_token_format(self) -> None:
        out = redact("sk-ant-abcdefghijklmnopqrst", mode="tokenize")
        assert out.startswith("<REDACTED:ANTHROPIC_KEY:")
        assert out.endswith(">")


class TestBalancedMode:
    def test_keeps_visible_chars(self) -> None:
        out = redact("Bearer ABCDEFGHIJ0123456789", mode="balanced")
        # First 2 + last 4 visible
        assert "Be" in out
        assert "6789" in out

    def test_short_value_fully_masked(self) -> None:
        out = redact("AKIAABCD12345EFGHI88", mode="balanced")
        # Long enough to use the partial mask
        assert "*" in out


class TestEmptyAndNoMatch:
    def test_empty_string_returns_empty(self) -> None:
        assert redact("", mode="strict") == ""

    def test_no_secrets_unchanged(self) -> None:
        text = "Just a plain text message with no secrets at all."
        assert redact(text, mode="strict") == text


class TestCreditCardLuhn:
    def test_valid_luhn_redacted(self) -> None:
        # Test card number 4111 1111 1111 1111 passes Luhn
        out = redact("4111-1111-1111-1111", mode="strict")
        assert "<REDACTED:CREDIT_CARD>" in out

    def test_invalid_luhn_kept(self) -> None:
        # 4111 1111 1111 1112 fails Luhn → must NOT be redacted
        text = "4111-1111-1111-1112"
        out = redact(text, mode="strict")
        assert "<REDACTED:CREDIT_CARD>" not in out


class TestRedactDict:
    def test_recurses_into_mapping(self) -> None:
        obj = {"a": "Bearer ABCDEFGHIJ0123456", "b": [{"c": "alice@x.com"}]}
        out = redact_dict(obj, mode="strict")
        assert "<REDACTED:BEARER_TOKEN>" in str(out["a"])
        assert "<REDACTED:EMAIL>" in str(out["b"][0]["c"])

    def test_preserves_non_strings(self) -> None:
        obj = {"x": 1, "y": True, "z": None, "lst": [2, 3]}
        out = redact_dict(obj, mode="tokenize")
        assert out == obj


class TestFindSecrets:
    def test_returns_kind_and_value(self) -> None:
        secrets = find_secrets("My key sk-ant-1234567890abcdefghij is leaked")
        kinds = [k for k, _ in secrets]
        assert "ANTHROPIC_KEY" in kinds

    def test_empty_returns_empty(self) -> None:
        assert find_secrets("") == []
        assert find_secrets("nothing to see") == []

    def test_credit_card_luhn_filtering(self) -> None:
        # Invalid Luhn skipped
        out = find_secrets("4111-1111-1111-1112")
        assert all(k != "CREDIT_CARD" for k, _ in out)


class TestSerializeTrajectory:
    def test_string_passthrough(self) -> None:
        assert serialize_trajectory("hello") == "hello"

    def test_dict_list_to_json(self) -> None:
        out = serialize_trajectory([{"role": "user", "content": "hi"}])
        assert "user" in out
        assert "hi" in out
