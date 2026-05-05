*** Settings ***
Documentation    exp_13b — confirms RF resolves ``Library <module>`` to a
...              class whose name equals the module's last segment.
Library          tests.experiments.exp_13b.MCP

*** Test Cases ***
Implicit Class Resolution Works When Class Matches Module
    [Tags]    exp13b    facade    pattern
    ${result}=    MCP Hello
    Should Be Equal As Strings    ${result}    MCP-facade-works
