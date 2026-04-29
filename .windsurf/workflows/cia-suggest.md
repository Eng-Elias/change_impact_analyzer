---
description: Find untested code using CIA and write the missing tests
---

1. Call the `cia_suggest_tests` MCP tool to get CIA's coverage gap report.

2. If CIA reports no gaps, say "CIA found all changed code has test coverage."

3. For each entity CIA flagged as untested:
   a. Read the source file CIA identified.
   b. Analyze the function/method signature, parameters, and return type.
   c. Write a pytest test class with:
      - A happy-path test
      - An edge-case test (empty input, boundary values)
      - An error-handling test if the function can raise exceptions
   d. Place it in the file path CIA suggested.

4. Show the generated test code and ask if the user wants to create the files.
