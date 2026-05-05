*** Settings ***
Documentation    exp_13 — does ``Library <module>`` resolve to a class
...              whose name matches the LAST segment of the module path?
...              And does ``Library <module>.<ClassName>`` resolve to the
...              specific class regardless of module name?
Library          tests.experiments.exp_13_facade_proof
Library          tests.experiments.exp_13_facade_proof.Probe    WITH NAME    Explicit

*** Test Cases ***
Implicit Class Resolution — Library Module Name
    [Tags]    exp13    facade    implicit
    # `Library tests.experiments.exp_13_facade_proof` — RF should pick the
    # class named after the last segment of the module path? Or the first
    # class found with @keyword methods? This is what we're proving.
    ${info}=    Probe Get Info
    Should Be Equal As Strings    ${info}[facade]    Probe

Explicit Class Resolution — Library Module.Class
    [Tags]    exp13    facade    explicit
    ${info}=    Explicit.Probe Get Info
    Should Be Equal As Strings    ${info}[facade]    Probe

Add Via Implicit Import
    [Tags]    exp13    facade
    ${result}=    Probe Add    5    7
    Should Be Equal As Integers    ${result}    12
