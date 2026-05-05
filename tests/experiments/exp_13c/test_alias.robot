*** Settings ***
Documentation    exp_13c — confirms RF resolves ``Library <module>`` to a
...              re-aliased class via ``from ... import X as <ModuleName>``.
Library          tests.experiments.exp_13c.MCP

*** Test Cases ***
Aliased Class Imports Cleanly
    [Tags]    exp13c    facade    alias
    ${result}=    MCP Hello
    Log    ${result}
    Should Contain    ${result}    name-attr-on-class=
