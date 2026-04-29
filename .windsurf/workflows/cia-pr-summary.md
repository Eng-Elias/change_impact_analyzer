---
description: Generate a PR description from CIA's analysis
---

1. Call `cia_analyze` to get CIA's risk report for current changes.

2. Call `cia_detect_changes` to get the list of changed files and symbols.

3. Call `cia_predict_tests` to find affected tests.

4. Write a structured PR description with:
   - **Summary**: what changed, module by module (from CIA's change detection)
   - **Risk**: CIA's overall score and level
   - **Impact**: blast radius (affected modules from CIA's report)
   - **Tests**: which tests cover this change (from CIA's prediction)
   - **Coverage**: any gaps CIA found
