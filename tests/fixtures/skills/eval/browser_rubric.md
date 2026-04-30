# Browser Skill Rubric

Score the assistant's response **PASS** when **all** of the following hold; otherwise **FAIL**:

1. The output is valid Robot Framework syntax (Settings/Test Cases/Keywords sections, `Library`, indentation by spaces).
2. It uses the `Browser` library keywords (`New Browser`, `New Page`, `Get Title`, `Click`, `Fill Text`, `Take Screenshot`, `Wait For Elements State`).
3. It uses explicit assertions (`Should Contain`, `Should Be Equal`, `Get Title    ==`).
4. It does NOT invoke `SeleniumLibrary` keywords (the project pins `Browser`).
5. It does NOT contain hard-coded `Sleep` waits longer than 1s.

When uncertain, prefer **FAIL** over **PASS** — false-pass is worse than false-fail.
