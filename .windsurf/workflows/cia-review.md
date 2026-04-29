---
description: Run a full pre-commit review using CIA's analysis
---

1. Call the `cia_analyze` MCP tool to get CIA's risk report for staged changes.

2. Call the `cia_predict_tests` MCP tool to find which tests CIA says are affected.

3. Call the `cia_suggest_tests` MCP tool to find coverage gaps CIA detected.

4. Synthesize CIA's results into a structured review:
   - **Risk Score**: CIA's overall score, level, and top contributing factors
   - **Blast Radius**: number of affected modules from CIA's report
   - **Tests to Run**: the pytest command from CIA's test prediction
   - **Coverage Gaps**: entities CIA flagged as untested
   - **Verdict**: based on CIA's risk level:
     - Score < 26: LOW -- safe to commit
     - Score 26-50: MEDIUM -- run affected tests first
     - Score 51-75: HIGH -- add tests or split the commit
     - Score 76+: CRITICAL -- do not commit without review
