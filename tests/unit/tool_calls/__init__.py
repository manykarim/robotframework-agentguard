"""Tool-call (BFCL AST) unit tests.

Keywords (research §3.1, ADR-004):
- Tool Call Should Match Name           (exact string)
- Tool Call Arguments Should Match      (AST equality, schema-normalised)
- Required Parameters Should Be Present (JSON schema)
- Parallel Tool Calls Should Match      (multiset)
- Tool Sequence Should Match            (ordered subsequence with wildcards)
- Should Not Call Any Tool              (decide-not-to-act)
- BFCL Score Should Be Above            (aggregated dataset score)
"""
