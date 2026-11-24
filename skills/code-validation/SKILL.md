---
name: code-validation
description: Validate Python files against the project's code-structure and formatting rules, and apply the shared faithful comment-story requirements. Use when asked to write, modify, check, lint, validate, or mechanically fix Python code governed by the project's conventions; use the code-review skill for language-independent semantic reviews.
---

# Code validation

This skill provides command-line validation and conservative fixing for Python code structure and formatting. It delegates semantic comment-story review to the language-independent code-review skill.

When creating or modifying Python files, consult the rules below **before**
writing. Apply the rules proactively rather than writing code and then fixing it. The validator is only a mechanical check, not a cleanup tool or a substitute for the semantic comment-fidelity review.

## For the AI assistant: write it correctly the first time

Before generating or editing any Python file in this project, run through this mental checklist. If a rule applies to the line you are about to write, apply it immediately.

- [ ] **Header**: first line is `# <project>/<relative/path>.py`.
- [ ] **Imports**: contiguous block, no blank lines inside it, local imports last and alphabetically sorted.
- [ ] **Class panels**: every `class ` is preceded by the exact 20-char panel.
- [ ] **Module story**: a comment block directly after the file header explains the module's purpose, role in the wider flow, and important dependencies, state, or side effects.
- [ ] **Class story**: each class has a high-level comment narrative describing its responsibility, role in the wider flow, and important state, collaborations, guarantees, or side effects.
- [ ] **Function/method story**: functions and methods have lead comments that explain their contract and the sequence of meaningful work they perform. As a rule of thumb, start the block with `# Function[Method]: Description` (respect the upper cases), `# Helper Function[Method]: Description`, `# Internal Function[Method]: Description`, `# Public Function[Method]: Description`, etc. You can use other function or method describers if they make sense. The block may span multiple consecutive comment lines; at least one line must carry the tag, and no blank line may separate the block from the definition or its decorators. `async def` definitions follow the same rule.
- [ ] **Meaningful comments**: comments let developers understand the implementation without reading the actual code lines. They must explain concrete behavior, not restate a definition's name, as in the useless `# Function: get create table` above `def get_create_table(...)`.
- [ ] **Chunk comments**: every meaningful code chunk, including chunks after blank lines, starts with a comment explaining what that chunk accomplishes and why it is needed in the flow.
- [ ] **Comment fidelity**: every comment has been checked against the code it describes and accurately reflects its operations, order, branches, side effects, and failure behavior.
- [ ] **Comment length**: no comment line exceeds 128 columns.
- [ ] **Alignment**: multi-line keyword args and dict entries are vertically aligned.
- [ ] **Blank lines**: never leave double blank lines.

## Comment-story review

Load and follow the language-independent **code-review** skill for the required module/file, class/component, function/method, and instruction/block narratives and the semantic fidelity review. Mechanical validation is not a substitute for that process.

Apply these Python placement rules so the complete story is visible in `#` comments:

- Put the **module story** directly after the required file header and before imports.
- Put each **class story** directly before its three-line class panel. The panel must remain immediately before the first decorator, or immediately before the class when no decorator is present.
- Put each **function/method story** in its tagged lead-comment block above decorators; the tag identifies the actual module, nested-function, or class scope.
- Put each **instruction/block story** in explanatory comments before the statements it describes.
- Do not leave any part of the required narrative only in a docstring. Docstrings can provide caller documentation but do not replace the comment-only review story.

## Rules

Before running the validator, check the target file against these conventions.

### File header

- The first line must be a comment containing the path of the file relative to the project root.
- The path must start with the project name from `[project].name` in
  `pyproject.toml`.
- Use POSIX `/` path separators.

Example:

~~~python
# graphregistry/adapters/persistence/mysql/repositories/edge_repository.py
~~~

### Imports

- Imports must form a contiguous block near the beginning of the file.
- Do not place blank lines between import statements.
- Local project imports must appear at the end of the import section.
- Local project imports must be ordered alphabetically.

### Class definitions

- Class definitions must be preceded by the project's required class panel comment.
- Preserve the exact panel width and formatting expected by the validator.
- Immediately before the panel, add the high-level class narrative in consecutive `#` comments as required by the code-review skill.
- For an undecorated class, keep all three panel lines immediately adjacent to the class. For a decorated class, keep the panel immediately adjacent to the first decorator; decorators then lead directly to the class.
- Never place narrative comments or panels between a decorator and its class.
- Do not put the overview only in a docstring: it must be visible when a reviewer reads only the `#` comments.
- The structural panel alone is not a class story.

Example:

~~~python
# Store and retrieve examples using the backend selected by each entity's key.
# Storage is selected from the entity key rather than kept in process-local state;
# callers remain isolated from schema resolution and row mapping.
#==================#
# Class Definition #
#==================#
@dataclass
class ExampleRepository:
    ...
~~~

### Internal functions and methods

- Introduce single-underscore definitions with the tag matching their actual scope:

~~~python
# Internal Function: <description>  # module-level or nested function
# Internal Method: <description>    # class-scope method
~~~

- Dunder methods such as `__init__` are **not** excluded from the narrative requirement. Treat them as public protocol methods and use `# Public Method:` with a meaningful initialization or protocol-behavior story.
- When decorators are present, place the comment immediately before the first decorator.
- The lead comment may span multiple consecutive comment lines. At least one line of the block must open with the required prefix, and no blank line may separate the block from the definition or its decorators.
- The same rules apply to `async def` definitions.

Example:

~~~python
# Internal Method: Convert the database row to an edge
@staticmethod
def _row_to_edge(row):
    ...
~~~

### Public functions and methods

- Introduce public definitions with the tag matching their actual scope:

~~~python
# Public Function: <description>    # module-level or nested function
# Public Method: <description>      # class-scope method or dunder protocol method
~~~

- When decorators are present, place the comment immediately before the first decorator.
- The lead comment may span multiple consecutive comment lines. At least one line of the block must open with the required prefix, and no blank line may separate the block from the definition or its decorators.
- The same rules apply to `async def` definitions.

Examples:

~~~python
# Public Function: Retrieve an edge by its key
@cache
def get_edge(key):
    ...
~~~

~~~python
class ExampleRepository:
    # Public Method: Initialize the repository with its deterministic backend resolver
    def __init__(self, resolver):
        ...
~~~

### Code chunks

- Every chunk of code separated from the previous chunk by a blank line must start with an explanatory `#` comment where required by the validator.
- Also introduce a new chunk comment whenever the implementation moves to a new meaningful step, even if no blank line is present.
- Triple-quoted multiline strings and docstrings are excluded from this structural analysis, but their behavior still belongs in the surrounding comment story.
- Comments must tell the reader **what behavior the following chunk implements**, why that step exists, and how it fits into the overall flow. Together they must provide the instruction-level story described above.
- Do not add comments that merely echo syntax or restate names (e.g. `# Check the if clause.`, `# Return the result.`, `# Do the next step.`). Describe the concrete outcome and its business or algorithmic purpose instead.
- Ensure each comment matches the precise branch, data, operation order, and side effects of its chunk. Move or rewrite it when the chunk moves or changes.
- Never insert placeholder, tag-only, or generic filler comments to satisfy validation. If the story is missing, the responsible agent must read the implementation and write the actual narrative before rerunning validation. A TODO or placeholder does not make the code reviewable and never resolves the failure.

Example of bad vs. good chunk comments:

~~~python
# Bad: restates the code, adds no meaning.
# Handle the conditional case.
if do_commit:
    ...

# Good: explains the business intent.
# Persist the node inside a new session when the caller asked for a commit.
if do_commit:
    ...
~~~

~~~python
# Bad: generic filler.
# Return the computed result.
return NodeList(item_list=nodes)

# Good: explains what the returned value represents.
# Return the saved nodes as a NodeList.
return NodeList(item_list=nodes)
~~~

### Comment length

- Comment lines must not exceed 128 columns.
- Tabs count according to their expanded display width.
- If a comment would exceed 128 columns, split it across multiple comment lines.

Example:

~~~python
# Convert each edge to a basic row representation using the mapper and prepare
# the resulting dictionaries for upserting.
~~~

### Function group panels

Function groups must use the exact panel format:

~~~python
#================================================================#
# Function Group: <description>                                  #
#================================================================#
~~~

- The panel has 64 characters between its outer `#` characters.
- Pad the description line with spaces before the final `#`.
- Preserve the indentation level of the surrounding code.
- Leave exactly one blank line between the panel and the next comment or definition.

### Method group panels

Method groups must use the exact panel format:

~~~python
#================================================================#
# Method Group: <description>                                    #
#================================================================#
~~~

- The panel has 64 characters between its outer `#` characters.
- Pad the description line with spaces before the final `#`.
- Preserve the indentation level of the surrounding code.
- Leave exactly one blank line between the panel and the next comment or definition.

### Keyword argument alignment

When a function call contains multiple consecutive keyword arguments on separate lines, vertically align their `=` separators.

Use:

~~~python
self._upsert_rows(
    session          = session,
    table_path       = table_path,
    key_column_names = key_columns,
    upd_column_names = update_columns,
    rows             = rows,
)
~~~

Do not use:

~~~python
self._upsert_rows(
    session=session,
    table_path=table_path,
    key_column_names=key_columns,
    upd_column_names=update_columns,
    rows=rows,
)
~~~

### Dictionary alignment

When a dictionary contains multiple consecutive string-literal keys on separate lines, vertically align their `:` separators.

Use:

~~~python
{
    "from_object_type" : edge.key.from_object_type,
    "from_object_id"   : edge.key.from_object_id,
    "to_object_type"   : edge.key.to_object_type,
    "to_object_id"     : edge.key.to_object_id,
    "context"          : edge.key.context,
    **basic_row,
}
~~~

- `**mapping` entries are excluded from alignment.
- Non-string and computed dictionary keys are not subject to this rule.

## New file template

When creating a new Python file, mirror this layout. Do not leave sections empty or skip the required comments.

~~~python
# graphregistry/adapters/persistence/mysql/repositories/example.py
# Persist Example entities in their key-selected backend. This module keeps
# schema resolution and SQL identifier quoting behind the repository boundary.
from __future__ import annotations
from typing import TYPE_CHECKING
from graphregistry.adapters.persistence.mysql.session import MySQLSession
from graphregistry.domain.models.entities.mdl_example import Example

# Import GraphDB only during type checking to avoid a runtime circular import.
if TYPE_CHECKING:
    from graphdb.core.graphdb import GraphDB

# Persist examples in the backend selected by each entity's key while keeping
# schema resolution and database naming away from callers.
#==================#
# Class Definition #
#==================#
class ExampleRepository:

    # Internal Method: Quote both identifier parts so the resulting table path
    # can be used safely in SQL without changing which schema and table are named.
    @staticmethod
    def _qt(schema_name: str, table_name: str) -> str:
        return f"`{schema_name}`.`{table_name}`"

    # Public Method: Persist an example in the storage associated with its key and
    # return that same example so callers can continue a fluent operation chain.
    # Resolve the destination before constructing or issuing the database write.
    def save(self, example: Example) -> Example:
        # Resolve the engine and schema from the key so the write cannot default to
        # an unrelated backend when multiple destinations are configured.
        engine_name, schema_name = self._resolver.for_key(example.key)

        # Qualify the destination table with the resolved schema while quoting both parts.
        table_path = self._qt(schema_name, "examples")

        # Delegate the upsert with the resolved destination, then return the unchanged
        # input entity as promised by this method's fluent-interface contract.
        self._upsert(engine_name, table_path, example)
        return example
~~~

## Running the validator

The validator is bundled with this skill and lives in the skill's base directory. It requires Python 3.11 or newer for `tomllib` and the third-party `rich` package for formatted output; ensure `rich` is available in the Python environment before invoking it.

~~~bash
python ~/.config/opencode/skills/code-validation/code_validator.py <path/to/file.py>
~~~

The module also exposes `main(argv=None) -> int` and is import-safe, so tests can call it without argument parsing, file access, output, or process exit occurring during import.

The command exits with code 0 when the file passes, 1 when style violations are
found, and 2 when the file cannot be validated at all (missing `pyproject.toml`,
unreadable file, or syntax error), so it can gate CI, pre-commit hooks, and
shell chains.

The target file must belong to a project containing a `pyproject.toml` in one of its parent directories.

The `pyproject.toml` must contain:

~~~toml
[project]
name = "<project-name>"
~~~

The validator searches upward from the target file for the nearest
`pyproject.toml`.

## Automatic fixing

A mechanical fixer is also bundled with this skill:

~~~bash
python ~/.config/opencode/skills/code-validation/code_fixer.py <path/to/file.py>
~~~

By default it runs in dry-run mode and prints a unified diff of the changes it would make without writing the source file or creating a backup. Use `--write` only after reviewing that diff to apply the changes in place:

~~~bash
python ~/.config/opencode/skills/code-validation/code_fixer.py --write <path/to/file.py>
~~~

Additional options:

- `--check`: run `code_validator.py` on each changed file after writing.
- `--no-backup`: skip the `.bak` backup created next to each modified file.

The fixer performs deterministic textual transformations: headers, blank lines,
structural class panels, existing lead-comment tags, unambiguous single-line
keyword/dict separator alignment, and existing long-comment splitting. It does
not reorder imports. Multiline-string contents are excluded from textual rewrites,
resulting string literal values are compared against the input, and `ast.parse`
must succeed before writing. Each input file resolves its own nearest
`pyproject.toml`.

**The fixer never writes behavioral comments.** It has no chunk-comment generation
option and does not derive lead narratives from docstrings, function names, or
placeholders. Inserting the exact structural class panel does not satisfy the
class-story requirement. Existing comment descriptions can be normalized or
wrapped, but missing class, function/method, or block narratives are left missing.

Always review the full dry-run or post-write diff. If validation or review reports
missing or meaningless comments, stop and write the real implementation-faithful
narrative as the responsible agent. Then rerun validation and the code-review
process. There is no automatic-comment, placeholder, or TODO shortcut to approval.

## Validation workflow

When writing or modifying a Python file:

1. Consult the rules in this skill before making changes.
2. Apply the applicable rules while writing the code.
3. Run the validator on the modified file.
4. Read every validation error reported by the validator.
5. Fix all reported violations without undoing unrelated user code or comments.
6. Run the validator again.
7. Repeat until validation succeeds.
8. Perform the code-review skill's comment-only review at module/file, class/component, function/method, and instruction/block levels.
9. Compare the complete narrative with the implementation and correct inaccurate, incomplete, or stale comments. Formatting success alone is not approval.

Do not stop after fixing only the first reported problem if additional
validation errors remain.

Do not delete existing comments merely to make validation pass unless the user
explicitly requests their removal. Prefer correcting their formatting,
placement, or line length.

## When validation fails

Treat the validator output as the authoritative description of concrete
formatting violations.

Fix each reported issue and rerun the validator. If a validator requirement
appears to conflict with these documented rules, follow the validator's actual
behavior and update this skill when appropriate.

## Running the regression tests

From the `graphagents` repository root, run:

~~~bash
python -m pytest skills/code-validation/tests
~~~

The tests cover import-safe validator startup, exit statuses, module/class story
layout, decorated and nested classes, empty and invalid projects, multiline-string
preservation, literal and AST preservation, conservative alignment, independent
project roots, write-free dry-run diffs, removal of the chunk-comment CLI, and the
absence of every behavioral-comment generation path. Existing lead tags are
normalized for public, private, async, nested, and dunder definitions without
inventing narratives.
