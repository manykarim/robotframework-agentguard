*** Settings ***
Documentation    Acceptance — top-level AgentGuard Library composes all Phase-1 modules.
Library          AgentGuard    provider=mock

*** Variables ***
${GOOD_SKILL}    ${CURDIR}/../fixtures/skills/good-skill
${INJECTION}     ${CURDIR}/../fixtures/security/injection-skill

*** Test Cases ***
Library Loads All Six Components
    [Tags]    library    smoke
    ${info}=    Get AgentGuard Info
    Should Contain    ${info}[components]    MCPKeywords
    Should Contain    ${info}[components]    SkillsKeywords
    Should Contain    ${info}[components]    ToolCallKeywords
    Should Contain    ${info}[components]    StatsKeywords
    Should Contain    ${info}[components]    JudgeKeywords
    Should Contain    ${info}[components]    SecurityKeywords

Skill Loads And Validates
    [Tags]    skills    smoke
    ${skill}=    Load Skill    ${GOOD_SKILL}
    Validate Skill Frontmatter    ${skill}

Injection Skill Fails Security Scan
    [Tags]    security    smoke
    ${report}=    Scan Skill    ${INJECTION}
    Should Be Equal As Strings    ${report.decision}    deny

Stats Keywords Work End-To-End
    [Tags]    stats    smoke
    ${a}=    Evaluate    [1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0,10.0]
    ${b}=    Evaluate    [0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0]
    Cliffs Delta Should Be At Least    ${a}    ${b}    delta=0.3
    ${ci}=    Bootstrap Confidence Interval    ${a}    statistic=mean    confidence=0.95
    Should Be True    ${ci}[0] > 0

BFCL Tool Call Matchers Work Offline
    [Tags]    tool_calls    smoke
    ${actual}=    Create Dictionary    name=search    arguments={"q": "robot"}
    Tool Call Should Match Name    ${actual}    search
    Tool Call Arguments Should Match    ${actual}    {"q": "robot"}    mode=ast

Redactor Masks Secrets
    [Tags]    security    redactor
    ${redacted}=    Redact Trajectory    Bearer abcdefgh12345678XX    mode=tokenize
    Should Not Contain    ${redacted}    abcdefgh
