"""Tests for `AgentGuard.skills.parser` — `SKILL.md` frontmatter + body parsing.

Public surface: `parse_skill`, `parse_skill_text`, `validate_skill`,
`Skill` dataclass, `SKILL_NAME_RE`, `SkillParseError`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from AgentGuard.skills.parser import (
    SKILL_NAME_RE,
    Skill,
    SkillParseError,
    parse_skill,
    parse_skill_text,
    validate_skill,
)


def _write(path: Path, frontmatter: dict, body: str = "Body.") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        "---\n" + yaml.safe_dump(frontmatter) + "---\n" + body + "\n",
        encoding="utf-8",
    )
    return path


class TestParseSkillText:
    def test_basic(self) -> None:
        text = "---\nname: my-skill\ndescription: A demo\n---\nBody line 1\n"
        s = parse_skill_text(text)
        assert s.name == "my-skill"
        assert s.description == "A demo"
        assert "Body line 1" in s.body

    def test_allowed_tools_list(self) -> None:
        text = "---\nname: x\ndescription: y\nallowed-tools: [Read, Write]\n---\nbody\n"
        s = parse_skill_text(text)
        assert s.allowed_tools == ["Read", "Write"]

    def test_allowed_tools_csv(self) -> None:
        text = "---\nname: x\ndescription: y\nallowed-tools: Read, Write\n---\nbody\n"
        s = parse_skill_text(text)
        assert s.allowed_tools == ["Read", "Write"]

    def test_no_frontmatter_raises(self) -> None:
        with pytest.raises(SkillParseError):
            parse_skill_text("Just body, no frontmatter.")

    def test_unclosed_frontmatter_raises(self) -> None:
        with pytest.raises(SkillParseError):
            parse_skill_text("---\nname: x\nNo closing line\n")

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(SkillParseError):
            parse_skill_text("---\n: : :\n---\nbody\n")

    def test_missing_name_raises(self) -> None:
        with pytest.raises(SkillParseError):
            parse_skill_text("---\ndescription: y\n---\nbody\n")

    def test_missing_description_raises(self) -> None:
        with pytest.raises(SkillParseError):
            parse_skill_text("---\nname: x\n---\nbody\n")

    def test_unknown_keys_warn(self) -> None:
        text = "---\nname: x\ndescription: y\nunknown-key: value\n---\nbody\n"
        with pytest.warns(UserWarning, match="Unknown SKILL.md frontmatter key"):
            s = parse_skill_text(text)
        assert s.extra_frontmatter == {"unknown-key": "value"}

    def test_invalid_allowed_tools_type_raises(self) -> None:
        text = "---\nname: x\ndescription: y\nallowed-tools: 42\n---\nbody\n"
        with pytest.raises(SkillParseError):
            parse_skill_text(text)


class TestParseSkill:
    def test_parses_directory(self, tmp_path: Path) -> None:
        d = _write(tmp_path / "good", {"name": "good-skill", "description": "ok"})
        s = parse_skill(d)
        assert s.name == "good-skill"
        assert s.source_path == d / "SKILL.md"

    def test_parses_md_file(self, tmp_path: Path) -> None:
        d = _write(tmp_path / "g", {"name": "ok-name", "description": "yes"})
        s = parse_skill(d / "SKILL.md")
        assert s.name == "ok-name"

    def test_missing_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_skill(tmp_path / "nope")

    def test_enumerates_assets(self, tmp_path: Path) -> None:
        d = _write(tmp_path / "with-assets", {"name": "with-assets", "description": "x"})
        (d / "scripts").mkdir()
        (d / "scripts" / "x.py").write_text("print('hi')")
        (d / "references").mkdir()
        (d / "references" / "doc.md").write_text("ref")
        (d / "assets").mkdir()
        (d / "assets" / "img.txt").write_text("data")
        s = parse_skill(d)
        assert any("x.py" in str(p) for p in s.scripts)
        assert any("doc.md" in str(p) for p in s.references)
        assert any("img.txt" in str(p) for p in s.assets)

    def test_uses_existing_fixture(self) -> None:
        fixtures = Path(__file__).parent.parent.parent / "fixtures" / "skills"
        s = parse_skill(fixtures / "good-skill")
        assert s.name == "good-example"
        assert s.allowed_tools == ["Read", "Write"]

    def test_bad_fixture_raises(self) -> None:
        fixtures = Path(__file__).parent.parent.parent / "fixtures" / "skills"
        with pytest.raises(SkillParseError):
            parse_skill(fixtures / "bad-skill")


class TestValidateSkill:
    def test_valid(self) -> None:
        s = Skill(name="ok-name", description="yes", body="hi")
        validate_skill(s)  # no raise

    def test_empty_name_raises(self) -> None:
        s = Skill(name="", description="y", body="b")
        with pytest.raises(SkillParseError):
            validate_skill(s)

    def test_invalid_name_pattern_raises(self) -> None:
        s = Skill(name="UPPER", description="y", body="b")
        with pytest.raises(SkillParseError, match="violates regex"):
            validate_skill(s)

    def test_empty_description_raises(self) -> None:
        s = Skill(name="ok-name", description="   ", body="b")
        with pytest.raises(SkillParseError):
            validate_skill(s)

    def test_blank_allowed_tool_raises(self) -> None:
        s = Skill(name="ok-name", description="y", body="b", allowed_tools=[""])
        with pytest.raises(SkillParseError):
            validate_skill(s)


class TestSkillNameRegex:
    @pytest.mark.parametrize(
        "name",
        ["abc", "abc-def", "good-skill", "a01-2-3-4-5"],
    )
    def test_valid_names(self, name: str) -> None:
        assert SKILL_NAME_RE.match(name)

    @pytest.mark.parametrize(
        "name",
        ["a", "ab", "Abc", "abc_def", "1abc", "-abc", "abc!"],
    )
    def test_invalid_names(self, name: str) -> None:
        assert not SKILL_NAME_RE.match(name)


class TestSkillToDict:
    def test_serialises_paths_to_strings(self, tmp_path: Path) -> None:
        s = Skill(name="x", description="y", body="b", source_path=tmp_path / "SKILL.md")
        d = s.to_dict()
        assert isinstance(d["source_path"], str)
        assert d["name"] == "x"
