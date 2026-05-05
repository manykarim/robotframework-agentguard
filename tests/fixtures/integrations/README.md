# Integration Fixtures

Sample artefacts for the two AgentGuard upstream integration suites.

| Source | Local path under here | Upstream |
|---|---|---|
| Agent Skill (script-based) | `skills/rf-libdoc-search/SKILL.md` | https://github.com/manykarim/robotframework-agentskills/tree/main/skills/robotframework-libdoc-search |
| Agent Skill (library-reference) | `skills/rf-browser-skill/SKILL.md` | https://github.com/manykarim/robotframework-agentskills/tree/main/skills/robotframework-browser-skill |

## Why bundled fixtures?

`tests/integration/test_agentskills_integration.py` runs in two modes:

1. **Default**: scan the bundled fixtures so the suite always has *something* to grade.
2. **Discovered**: if the upstream repo is checked out (auto-detected at the standard
   paths in `AgentGuard.skills.discovery`), tests additionally exercise every shipped
   skill — these tests are tagged so users without the upstream clone aren't blocked.

The bundled SKILL.md files are minimised + frontmatter-equivalent to upstream so
the parser/validator/scanner exercises real shapes without our suite carrying full
upstream content.

## rf-mcp

`tests/integration/test_rf_mcp_integration.py` does **not** need a local fixture —
it imports `robotmcp.server.mcp` (the module-level FastMCP instance) and binds an
in-process client using AgentGuard's `transport=memory` path. Install via
`uv add robotframework-agentguard[integrations]` or `pip install rf-mcp` to enable.
