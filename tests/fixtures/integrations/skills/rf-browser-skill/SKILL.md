---
name: rf-browser-skill
description: Robot Framework Browser Library reference — Playwright-based browser automation with deep selector support. Use when authoring or refactoring browser test cases that target the Browser library (not SeleniumLibrary).
---

# Robot Framework Browser Library Reference

Reference skill for the Browser Library (Playwright). Use the keywords from this
library to author headless or headed browser test cases.

## Common keywords

- `New Browser` — launch a browser instance.
- `New Context` — create an isolated browsing context.
- `New Page` — open a tab.
- `Click` — click an element by selector.
- `Fill Text` — type into an input.
- `Get Text` / `Get Element` / `Get Attribute` — assertions and retrieval.

## Recommended selectors

Prefer Playwright role selectors (`role=button[name="Submit"]`) and CSS over
XPath when the target is stable.

(Bundled fixture mirrored from
https://github.com/manykarim/robotframework-agentskills/tree/main/skills/robotframework-browser-skill.)
