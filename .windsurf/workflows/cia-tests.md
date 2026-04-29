---
description: Show tests CIA says are affected by current changes
---

1. Call the `cia_predict_tests` MCP tool to get affected tests.

2. Present the list of affected test files.

3. Show the pytest command to run them:
   ```
   pytest <pytest_args from CIA>
   ```

4. If no tests are affected, report that.
