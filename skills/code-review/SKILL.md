---
name: code-review
description: Review agent-generated source code through a coherent, verified comment-only narrative. Use when reviewing generated code, checking whether comments faithfully describe implementation behavior, or defining multi-level code-documentation standards in any programming language.
---

# Code review through comment stories

Use this skill to determine whether a reviewer can understand generated code by reading only its comments at progressively deeper levels, and whether that story is faithful to the implementation. It is language-independent; combine it with a language-specific validation skill for syntax, placement, and formatting rules.

## Narrative levels

Every applicable level must tell a coherent story on its own. Deeper levels add detail without contradicting higher-level accounts.

1. **Module/file level — the context.** Near the top of the file, explain its purpose, role in the wider workflow, important dependencies or collaborators, and externally visible state or side effects. Cover module-level orchestration, configuration, constants, and wiring as well as definitions. For a small single-purpose file, a concise paragraph is sufficient; do not repeat the file name as the whole story.
2. **Class/component level — the overview.** When the module contains classes or similar components, explain each abstraction's responsibility, collaborators or resources, meaningful state, guarantees, and side effects. Tell the story of what it accomplishes rather than listing member names. For functions-only modules, the module narrative provides this level of context.
3. **Function/method level — the chapter.** Explain the caller-visible inputs, outputs, and contract, then narrate meaningful work in actual execution order. Include consequential decisions, data transformations, I/O, mutations, returns, errors, retries, transactions, and cleanup. This is a behavioral narrative, not a copy of the function name or signature.
4. **Instruction/block level — the scenes.** Introduce each meaningful step with the behavior the statements accomplish together and why that step is needed. Explain branches, loops, calls, early returns, exception paths, mutations, and side effects in domain terms. Comment individual instructions only when the surrounding story does not make their behavior or rationale clear; do not mechanically translate every expression into pseudocode.

Write comments in the source language's normal comment syntax. Keep the narrative adjacent to the code it describes except where a language-specific convention requires a structural marker between the narrative and definition.

## Fidelity is a review gate

A fluent story is not necessarily true. Passing a structural validator establishes neither semantic completeness nor accuracy.

Review each affected module, class/component, and function/method as follows:

1. **Read only the comments.** Start with file context, then class overviews, function/method chapters, and block scenes. Confirm that the chosen level can be understood without reconstructing missing behavior from implementation tokens.
2. **Compare claims with execution.** Check every behavioral statement against actual operations and their order. Verify data transformations, branch predicates, loop behavior, external calls, mutations, return values, exceptions, retries, transactions, cleanup, concurrency behavior, and other side effects that apply.
3. **Find misleading omissions.** Check that the story covers unsuccessful and exceptional paths as well as the happy path. A technically true comment that hides an early return, swallowed exception, commit, fallback, retry, or external side effect is not faithful.
4. **Check cross-level consistency.** Details must support, not contradict, the surrounding contract or class/module overview. Correct duplicated summaries when one copy becomes stale.
5. **Reject filler and placeholders.** Name-restating comments, generic conditional/return comments, tag-only comments, TODO narratives, aspirational descriptions of unimplemented behavior, and copied stale docstrings are findings, not acceptable narrative.
6. **Re-review after edits.** Update every affected narrative when code changes. Comments follow implementation; do not change correct code merely to agree with an outdated comment.

Only after this comparison is comment-based trust justified.

## No placeholder shortcut

Never insert automatic or generic comments to make a checker pass. If a required story is missing or meaningless, the responsible agent must inspect the implementation and write the actual narrative before rerunning validation and review. A missing-comment finding remains blocking until that work is done. Review tooling may flag missing narratives but must not manufacture them.

## Review output

For each finding, report:

- the file and affected definition or block;
- the relevant narrative level;
- whether the problem is missing context, vague wording, an inaccurate claim, a misleading omission, or cross-level contradiction;
- the actual code behavior; and
- the corrected narrative needed for approval.

Treat missing or unfaithful stories as blocking findings for generated code. Mechanical style fixes do not resolve semantic findings.

## Boundaries

- Do not infer behavior from names alone; inspect the statements and their relevant callees or contracts when behavior is ambiguous.
- Do not certify fidelity by reading comments alone. Comment-only reading checks coherence; reading the implementation is still necessary to earn trust.
- Do not add comments to generated strings or data as though they were source comments.
- Preserve unrelated code and existing accurate comments while correcting narrative defects.
