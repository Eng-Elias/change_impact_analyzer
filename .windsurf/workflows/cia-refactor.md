---
description: CIA-guided safe refactoring with verification
---

1. Ask the user what symbol they want to refactor and what action (rename, move, extract).

2. Call `cia_get_dependents` with the module containing the symbol to find
   everything that depends on it.

3. Call `cia_graph` to understand the exact import edges.

4. Build a refactoring checklist:
   - Every file that imports the symbol (from CIA's graph)
   - Every test that covers it (call `cia_predict_tests`)
   - Risk score for this refactor (call `cia_score_risk`)

5. Guide the refactoring step by step, updating each file.

6. After changes, call `cia_predict_tests` and suggest running the affected tests.
