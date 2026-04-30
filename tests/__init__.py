"""AgentGuard test root.

Layout:
    unit/         — fast, default-offline pytest unit tests per module.
    integration/  — composition tests; some are @pytest.mark.live.
    acceptance/   — Robot Framework `.robot` suites driving the public keywords.
    fixtures/     — shared sample skills / mcp servers / judge calibration sets.
"""
