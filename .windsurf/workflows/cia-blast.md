---
description: Show CIA's blast radius analysis for a module
---

1. Ask the user which module to analyze if not provided as an argument.

2. Call the `cia_get_dependents` MCP tool with `transitive=true` for that module.

3. Call the `cia_graph` MCP tool with `output_format=json` to get context.

4. Present CIA's dependency data as:
   - Direct dependents (depth 1)
   - Transitive dependents (depth 2+)
   - Total count
   - Risk assessment based on the number of dependents
   - Which tests would need to run if this module changes
