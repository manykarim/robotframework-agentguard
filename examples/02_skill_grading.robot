*** Settings ***
Documentation    Phase-1 example mirroring research §6.2 — skill grading.
...              Uses a fixture skill + mockllm/model so it passes offline.
Library          AgentGuard    provider=mock

*** Variables ***
${SKILL_PATH}    ${CURDIR}/../tests/fixtures/skills/good-skill

*** Test Cases ***
Skill Loads And Frontmatter Validates
    [Tags]    skills    smoke
    ${skill}=    Load Skill    ${SKILL_PATH}
    Validate Skill Frontmatter    ${skill}
    Should Be Equal As Strings    ${skill.name}    good-example

Skill Grading Smoke Run With Mockllm
    [Documentation]    N=3 mock reps; smoke-test that the wiring works end-to-end.
    [Tags]    skills    offline
    ${scorecard}=    Run Skill Eval    ${SKILL_PATH}
    ...    runs=3    model=mockllm/model    judge_model=mockllm/model
    ...    prompts=["What is 2+2?","Print hello"]
    Should Be Equal As Strings    ${scorecard.skill_name}    good-example
    Should Be True    ${scorecard.runs} >= 1
