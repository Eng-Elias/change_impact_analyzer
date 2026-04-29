---
description: Architecture health audit using CIA's dependency graph
---

1. Call the `cia_graph` MCP tool with `output_format=json` to get CIA's dependency data.

2. From CIA's output, analyze:
   - **Circular dependencies**: cycles reported by CIA's graph
   - **God modules**: modules with more than 10 dependents in CIA's edges
   - **Orphan modules**: modules with no edges in CIA's graph
   - **Max depth**: longest dependency chain in CIA's graph

3. Score the project's architectural health from A (excellent) to F (poor).

4. For each issue found, provide:
   - Severity (critical / warning / info)
   - The specific modules involved (from CIA's data)
   - A concrete recommendation to fix it
