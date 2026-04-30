"""Unit tests for `AgentGuard.config`.

Covers: `load_env` (idempotent, missing-file warn, missing-dotenv warn),
`default_model`/`default_judge_model` env override, `feature_flag`,
`redact_env` masking of credential-shaped keys, `has_openrouter_key` boolean.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from AgentGuard import config


class TestLoadEnv:
    def test_loads_values_from_dotenv(self, tmp_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        config._loaded_paths.clear()
        config.load_env(tmp_env / ".env")
        import os
        assert os.environ.get("OPENROUTER_API_KEY") == "test"

    def test_idempotent_per_path(
        self, tmp_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config._loaded_paths.clear()
        config.load_env(tmp_env / ".env")
        # mutate env after first load; second load with override=False shouldn't change it
        monkeypatch.setenv("OPENROUTER_API_KEY", "second")
        config.load_env(tmp_env / ".env")
        import os
        assert os.environ["OPENROUTER_API_KEY"] == "second"

    def test_missing_file_warns_no_raise(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config._loaded_paths.clear()
        with caplog.at_level(logging.WARNING, logger="AgentGuard.config"):
            config.load_env(tmp_path / "missing.env")
        assert any("not found" in m for m in caplog.messages)

    def test_none_path_is_noop(self) -> None:
        # Should not raise.
        config.load_env(None)

    def test_missing_dotenv_module_warns(
        self,
        tmp_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        import builtins
        real_import = builtins.__import__

        def fake_import(name: str, *a: object, **kw: object) -> object:
            if name == "dotenv":
                raise ImportError("simulated missing dotenv")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        config._loaded_paths.clear()
        with caplog.at_level(logging.WARNING, logger="AgentGuard.config"):
            config.load_env(tmp_env / ".env")
        assert any("python-dotenv" in m for m in caplog.messages)


class TestDefaults:
    def test_default_model_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENTGUARD_DEFAULT_MODEL", raising=False)
        assert "claude" in config.default_model()

    def test_default_model_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTGUARD_DEFAULT_MODEL", "openrouter/foo/bar")
        assert config.default_model() == "openrouter/foo/bar"

    def test_default_judge_model_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTGUARD_JUDGE_MODEL", "openrouter/openai/gpt-4o-mini")
        assert config.default_judge_model() == "openrouter/openai/gpt-4o-mini"

    def test_default_judge_model_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENTGUARD_JUDGE_MODEL", raising=False)
        assert "gpt-4o-mini" in config.default_judge_model()


class TestFeatureFlag:
    @pytest.mark.parametrize("raw,expected", [
        ("1", True), ("true", True), ("YES", True), ("on", True),
        ("0", False), ("false", False), ("no", False), ("", False), ("garbage", False),
    ])
    def test_parses_truthy_values(
        self, monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
    ) -> None:
        monkeypatch.setenv("AGENTGUARD_TELEMETRY", raw)
        assert config.feature_flag("telemetry") is expected

    def test_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AGENTGUARD_NOTSET", raising=False)
        assert config.feature_flag("notset", default=True) is True
        assert config.feature_flag("notset", default=False) is False


class TestRedaction:
    def test_redact_masks_api_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-abcdef1234567890")
        monkeypatch.setenv("BENIGN_VAR", "value")
        out = config.redact_env()
        assert out["OPENROUTER_API_KEY"].startswith("****")
        assert out["OPENROUTER_API_KEY"].endswith("7890")
        assert out["BENIGN_VAR"] == "value"

    def test_redact_masks_token_secret_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TOKEN", "abcdefghij")
        monkeypatch.setenv("MY_SECRET", "abcdefghij")
        monkeypatch.setenv("MY_PASSWORD", "abcdefghij")
        out = config.redact_env()
        assert out["MY_TOKEN"] == "****ghij"
        assert out["MY_SECRET"] == "****ghij"
        assert out["MY_PASSWORD"] == "****ghij"

    def test_redact_short_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("X_API_KEY", "abc")
        monkeypatch.setenv("Y_API_KEY", "")
        out = config.redact_env()
        assert out["X_API_KEY"] == "****"
        assert out["Y_API_KEY"] == ""


class TestHasOpenRouterKey:
    def test_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-something")
        assert config.has_openrouter_key() is True

    def test_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        assert config.has_openrouter_key() is False

    def test_blank(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "   ")
        assert config.has_openrouter_key() is False
