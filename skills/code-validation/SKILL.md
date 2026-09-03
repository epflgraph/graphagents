---
name: code-validation
description: Validate Python files against the project's code-structure and formatting rules. Use when asked to write, modify, check, lint, or validate Python code governed by the project's conventions.
---

# Code validation

This skill provides a command-line validator that checks Python files against the project's code-structure and formatting conventions.

When creating or modifying Python files, consult the rules below **before**
writing. Apply the rules proactively rather than writing code and then fixing it. The validator is a final check, not a cleanup tool.

## For the AI assistant: write it correctly the first time

Before generating or editing any Python file in this project, run through this mental checklist. If a rule applies to the line you are about to write, apply it immediately.

- [ ] **Header**: first line is `# <project>/<relative/path>.py`.
- [ ] **Imports**: contiguous block, no blank lines inside it, local imports last and alphabetically sorted.
- [ ] **Class panels**: every `class ` is preceded by the exact 20-char panel.
- [ ] **Lead comments**: functions and method should have a comment above them describing what the function or method does. As a rule of thumb, start the description with `# Function[Method]: Description` (respect the upper cases), `# Helper Function[Method]: Description`, `# Internal Function[Method]: Description`, `# Public Function[Method]: Description`, etc.
- [ ] **Meaningful comments**: comments are meant to allow developers to go through the code, and understand what it does with explicitly reading the actual code lines. This means comments should actually be meaningful, and absolutely not low-IQ comments like "# Function: get create table \n def get_create_table(...)".
- [ ] **Chunk comments**: every code chunk after a blank line starts with a comment that explains *why* the chunk exists, not what the code does.
- [ ] **Comment length**: no comment line exceeds 128 columns.
- [ ] **Alignment**: multi-line keyword args and dict entries are vertically aligned.
- [ ] **Blank lines**: never leave double blank lines.

If you are unsure whether a comment is meaningful, read only the comments in order. They should tell a coherent story without reading the code.

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

Example:

~~~python
#==================#
# Class Definition #
#==================#
~~~

### Internal functions and methods

- Functions or methods whose names start with a single underscore must be preceded by:

~~~python
# Internal Function: <description>
~~~

- Dunder methods such as `__init__` are excluded from this rule.
- When decorators are present, place the comment immediately before the first decorator.

Example:

~~~python
# Internal Function: Convert the database row to an edge
@staticmethod
def _row_to_edge(row):
    ...
~~~

### Public methods

- Methods whose names do not start with `_` must be preceded by:

~~~python
# Public Method: <description>
~~~

- When decorators are present, place the comment immediately before the first decorator.

Example:

~~~python
# Public Method: Retrieve an edge by its key
@staticmethod
def get_edge(key):
    ...
~~~

### Code chunks

- Every chunk of code separated from the previous chunk by a blank line must start with an explanatory `#` comment where required by the validator.
- Triple-quoted multiline strings and docstrings are excluded from this analysis.
- Comments must tell the reader **why** the following chunk exists and how it fits into the overall flow. A reader should be able to skim the file as a story by reading only the comments.
- Do not add comments that merely restate the code (e.g. `# Check the if clause.`, `# Return the result.`, `# Do the next step.`). They must explain intent, context, or the business/algorithmic purpose of the chunk.
- Never leave auto-generated placeholder comments in committed code. Treat them as TODOs and rewrite them into meaningful prose before committing.

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

- Comment lines must not exceed 92 columns.
- Tabs count according to their expanded display width.
- If a comment would exceed 92 columns, split it across multiple comment lines.

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
from __future__ import annotations
from typing import TYPE_CHECKING

from graphregistry.adapters.persistence.mysql.session import MySQLSession
from graphregistry.domain.models.entities.mdl_example import Example

if TYPE_CHECKING:
    from graphdb.core.graphdb import GraphDB

#==================#
# Class Definition #
#==================#
class ExampleRepository:
    """Short purpose of the class."""

    # Internal Function: Build a safely quoted schema-qualified table name.
    @staticmethod
    def _qt(schema_name: str, table_name: str) -> str:
        return f"`{schema_name}`.`{table_name}`"

    # Public Method: Persist a single example and return it for chaining.
    def save(self, example: Example) -> Example:
        # Resolve the engine and schema for the example key.
        engine_name, schema_name = self._resolver.for_key(example.key)
        ...
~~~

## Running the validator

The validator is bundled with this skill:

~~~bash
python .opencode/skills/code-validation/code_validator.py <path/to/file.py>
~~~

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
python .opencode/skills/code-validation/code_fixer.py <path/to/file.py>
~~~

By default it runs in dry-run mode and prints the changes it would make. Use `--write` to apply the changes in place:

~~~bash
python .opencode/skills/code-validation/code_fixer.py --write <path/to/file.py>
~~~

Additional options:

- `--check`: run `code_validator.py` on each file after writing.
- `--add-chunk-comments`: insert placeholder comments before isolated code
  chunks. The placeholders are intentionally generic (e.g. `# Handle the
  conditional case.`) and **must be rewritten** before the code is committed.
  This flag is opt-in precisely because meaningful chunk comments require human
  judgment.
- `--no-backup`: skip the `.bak` backup created next to each modified file.

The fixer only applies safe, mechanical transformations: headers, blank lines,
class panels, comment prefixes, keyword/dict alignment, and long-comment
splitting. It validates the resulting file with `ast.parse` before writing and
refuses to write if a syntax error is introduced.

Always review the diff after running the fixer. When `--add-chunk-comments` is
used, every inserted comment must be rewritten so that the file reads as a
 coherent story; placeholder comments are not acceptable in committed code.

## Validation workflow

When writing or modifying a Python file:

1. Consult the rules in this skill before making changes.
2. Apply the applicable rules while writing the code.
3. Run the validator on the modified file.
4. Read every validation error reported by the validator.
5. Fix all reported violations without undoing unrelated user code or comments.
6. Run the validator again.
7. Repeat until validation succeeds.

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
