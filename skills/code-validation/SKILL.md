---
name: code-validation
description: Validate Python files against the project's code-structure and formatting rules. Use when asked to write, modify, check, lint, or validate Python code governed by the project's conventions.
---

# Code validation

This skill provides a command-line validator that checks Python files against
the project's code-structure and formatting conventions.

When creating or modifying Python files, consult the rules below before running
the validator. Apply the rules proactively rather than relying on the validator
to discover every issue afterward.

## Rules

Before running the validator, check the target file against these conventions.

### File header

- The first line must be a comment containing the path of the file relative to
  the project root.
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

- Class definitions must be preceded by the project's required class panel
  comment.
- Preserve the exact panel width and formatting expected by the validator.

Example:

~~~python
#==================#
# Class Definition #
#==================#
~~~

### Internal functions and methods

- Functions or methods whose names start with a single underscore must be
  preceded by:

~~~python
# Internal Function: <description>
~~~

- Dunder methods such as `__init__` are excluded from this rule.
- When decorators are present, place the comment immediately before the first
  decorator.

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

- When decorators are present, place the comment immediately before the first
  decorator.

Example:

~~~python
# Public Method: Retrieve an edge by its key
@staticmethod
def get_edge(key):
    ...
~~~

### Code chunks

- Every chunk of code separated from the previous chunk by a blank line must
  start with an explanatory `#` comment where required by the validator.
- Triple-quoted multiline strings and docstrings are excluded from this
  analysis.
- Do not add meaningless comments merely to satisfy the rule. Comments should
  describe the purpose of the following code chunk.

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

When a function call contains multiple consecutive keyword arguments on
separate lines, vertically align their `=` separators.

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

When a dictionary contains multiple consecutive string-literal keys on
separate lines, vertically align their `:` separators.

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

## Running the validator

The validator is bundled with this skill:

~~~bash
python .opencode/skills/code-validation/code_validator.py <path/to/file.py>
~~~

The target file must belong to a project containing a `pyproject.toml` in one
of its parent directories.

The `pyproject.toml` must contain:

~~~toml
[project]
name = "<project-name>"
~~~

The validator searches upward from the target file for the nearest
`pyproject.toml`.

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
