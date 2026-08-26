---
name: note-taking
description: Shared AI Wiki note-taking rules.
---

# Note Taking

- The `.opencode/wiki` directory is the shared knowledge base for all agents.
- Consult relevant AI Wiki notes before performing extensive code exploration, searches, greps, or repository scans.
- Prefer existing AI Wiki knowledge when it is sufficient to answer the current question or perform the current task.
- Create new notes when discovering important project knowledge that is likely to help future agents.
- Update existing notes when information becomes outdated, incomplete, or inaccurate.
- Improve notes written by other agents when doing so increases accuracy, clarity, or usefulness.
- Keep notes concise, factual, and implementation-focused.
- Record architectural decisions, conventions, workflows, dependencies, repository structure, and common pitfalls.
- Avoid storing transient information, temporary debugging results, or task-specific notes that are unlikely to be reused.
- Avoid duplicating information across multiple notes when a single note can be updated instead.
- Prefer updating an existing relevant note over creating a new overlapping note.
- Treat the AI Wiki as shared project memory rather than personal agent memory.
- When learning something that would otherwise require future code searches, consider documenting it in the AI Wiki.
- When a task requires understanding an unfamiliar area of the codebase, check the AI Wiki before scanning the repository.
- Keep notes technology-neutral when possible and repository-specific when necessary.
- Assume future agents may have no prior context beyond the AI Wiki and the current task.
