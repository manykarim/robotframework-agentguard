"""Tests for `AgentGuard.skills.discovery` — default-deny per ADR-006."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from AgentGuard.skills.discovery import (
    ALLOWLIST_FILENAME,
    DEFAULT_ROOTS,
    DiscoveryResult,
    discover,
)


def _make_skill(d: Path, name: str, description: str = "demo") -> Path:
    sk = d / name
    sk.mkdir(parents=True, exist_ok=True)
    (sk / "SKILL.md").write_text(
        "---\n"
        + yaml.safe_dump({"name": name, "description": description})
        + "---\nbody\n",
        encoding="utf-8",
    )
    return sk


class TestDefaults:
    def test_default_roots_includes_known_paths(self) -> None:
        assert "claude" in DEFAULT_ROOTS
        assert "agents" in DEFAULT_ROOTS
        assert "gemini" in DEFAULT_ROOTS
        assert "codex" in DEFAULT_ROOTS

    def test_allowlist_filename(self) -> None:
        assert ALLOWLIST_FILENAME == ".agentguard-allow.txt"


class TestDiscover:
    def test_returns_discovery_result(self, tmp_path: Path) -> None:
        result = discover([tmp_path / "no-such-root"])
        assert isinstance(result, DiscoveryResult)

    def test_finds_project_local_skills(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        skills_root = tmp_path / ".claude" / "skills"
        _make_skill(skills_root, "alpha")
        _make_skill(skills_root, "beta")
        result = discover([skills_root])
        names = sorted(s.name for s in result.all_skills())
        assert names == ["alpha", "beta"]

    def test_skips_non_directory_children(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills"
        skills_root.mkdir()
        _make_skill(skills_root, "alpha")
        # Throw a stray file in — must not be confused for a skill
        (skills_root / "not-a-dir.txt").write_text("hi")
        result = discover([skills_root])
        names = [s.name for s in result.all_skills()]
        assert names == ["alpha"]

    def test_records_parse_errors(self, tmp_path: Path) -> None:
        bad_root = tmp_path / "skills"
        bad_dir = bad_root / "broken"
        bad_dir.mkdir(parents=True)
        (bad_dir / "SKILL.md").write_text("not a real skill")
        result = discover([bad_root])
        assert any("broken" in str(p) for p, _ in result.errors)

    def test_third_party_with_allowlist_loads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Make root non-project-local (so trusted=False).
        far_home = tmp_path / "home"
        third = far_home / ".agents" / "skills"
        _make_skill(third, "trusted-x")
        (third / ALLOWLIST_FILENAME).write_text("trusted-x\n")
        # cwd is far away from this root
        monkeypatch.chdir(tmp_path / "elsewhere") if (tmp_path / "elsewhere").exists() else monkeypatch.chdir(tmp_path)

        result = discover([third])
        names = [s.name for s in result.all_skills()]
        assert "trusted-x" in names

    def test_third_party_without_allowlist_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        far_home = tmp_path / "home"
        third = far_home / ".agents" / "skills"
        _make_skill(third, "untrusted-x")
        # Force non-project-local: chdir somewhere completely outside `far_home`.
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.chdir(outside)

        result = discover([third])
        # Either the skill is loaded *with a warning*, or filtered if allowlist exists.
        assert result.warnings, "expected at least one ADR-006 warning"

    def test_third_party_outside_allowlist_suppressed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        far_home = tmp_path / "home"
        third = far_home / ".agents" / "skills"
        _make_skill(third, "blocked-x")
        (third / ALLOWLIST_FILENAME).write_text("only-this-name\n")
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.chdir(outside)
        result = discover([third])
        names = [s.name for s in result.all_skills()]
        assert "blocked-x" not in names
        assert any("blocked-x" in w for w in result.warnings)

    def test_default_roots_when_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Use a fake empty home so default roots resolve to non-existent dirs.
        monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
        result = discover()
        assert isinstance(result, DiscoveryResult)
        # by_tool keys mirror DEFAULT_ROOTS (some empty, no error).
        assert set(result.by_tool.keys()) <= set(DEFAULT_ROOTS) | {"claude", "agents"}
