*** Settings ***
Documentation    Phase-1 example — load, validate, security-scan, and offline-grade
...              skills from the manykarim/robotframework-agentskills catalogue
...              (https://github.com/manykarim/robotframework-agentskills).
...
...              Uses bundled fixtures under tests/fixtures/integrations/skills/
...              so it runs offline. The "Discovered Mode" tests below additionally
...              exercise an upstream clone if one is reachable at
...              ~/workspace/robotframework-agentskills.
Library          AgentGuard    provider=mock

*** Variables ***
${FIXTURE_ROOT}      ${CURDIR}/../tests/fixtures/integrations/skills
${LOCAL_CLONE}       ${EXECDIR}${/}..${/}robotframework-agentskills${/}skills

*** Test Cases ***
Bundled Libdoc Search Skill Loads
    [Tags]    agentskills    smoke
    ${skill}=    Load Skill    ${FIXTURE_ROOT}/rf-libdoc-search
    Validate Skill Frontmatter    ${skill}
    Should Be Equal As Strings    ${skill.name}    rf-libdoc-search

Bundled Browser Skill Loads
    [Tags]    agentskills    smoke
    ${skill}=    Load Skill    ${FIXTURE_ROOT}/rf-browser-skill
    Validate Skill Frontmatter    ${skill}
    Should Contain    ${skill.description}    Browser

Bundled Skill Passes Security Scan
    [Tags]    agentskills    security
    # ADR-006 default-deny rejects every unsigned skill; allow_unsigned=True
    # bypasses that policy gate so we assert on real CRITICAL findings only.
    ${report}=    Skill Should Pass Security Scan
    ...    ${FIXTURE_ROOT}/rf-libdoc-search    allow_unsigned=${True}    max_severity=HIGH
    ${crits}=    Evaluate    [f for f in $report.findings if f.severity.name == "CRITICAL"]
    Should Be Empty    ${crits}    msg=unexpected CRITICAL findings: ${crits}

Bundled Skill Grades Offline With Mockllm
    [Tags]    agentskills    offline
    ${scorecard}=    Run Skill Eval    ${FIXTURE_ROOT}/rf-libdoc-search
    ...    runs=1    model=mockllm/model    judge_model=mockllm/model
    ...    prompts=["Find a keyword that creates a temp file."]
    Should Be Equal As Strings    ${scorecard.skill_name}    rf-libdoc-search
    Should Be True    ${scorecard.runs} >= 1

Discovered Mode — Upstream Clone Validates Cleanly
    [Tags]    agentskills    upstream
    ${have}=    Evaluate    __import__('os').path.exists(r"${LOCAL_CLONE}")
    Skip If    not ${have}    no local agentskills clone at ${LOCAL_CLONE}
    ${count}=    Validate All Skills Under    ${LOCAL_CLONE}
    Should Be True    ${count} >= 3    only validated ${count} upstream skills

*** Keywords ***
Validate All Skills Under
    [Arguments]    ${root}
    ${entries}=    Evaluate    [str(p) for p in sorted(__import__('pathlib').Path(r"${root}").iterdir())]
    ${count}=    Set Variable    ${0}
    FOR    ${child}    IN    @{entries}
        ${has_skill}=    Evaluate    __import__('os').path.exists(r"${child}/SKILL.md")
        IF    ${has_skill}
            ${skill}=    Load Skill    ${child}
            Validate Skill Frontmatter    ${skill}
            ${count}=    Evaluate    ${count} + 1
        END
    END
    RETURN    ${count}
