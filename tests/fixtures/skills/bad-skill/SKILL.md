---
name: bad-example
allowed-tools:
  - Read
---

# Bad Example Skill

This fixture intentionally **omits the required `description` frontmatter key**
so the parser's validation path is exercised. It must raise
`SkillParseError` on `parse_skill(...)`.
