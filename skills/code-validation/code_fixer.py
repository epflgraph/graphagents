# graphregistry/.opencode/skills/code-validation/code_fixer.py
"""Mechanical fixer for the project's code-structure conventions.

This script applies safe, deterministic formatting fixes that mirror the checks
performed by ``code_validator.py``. It is intentionally conservative:

* It never changes program semantics.
* It validates the resulting file with ``ast.parse`` before writing.
* It runs in dry-run mode by default; use ``--write`` to persist changes.
* It backs up modified files in place with a ``.bak`` suffix when writing.

The fixer handles the mechanical rules (headers, blank lines, class panels,
comment prefixes, keyword/dict alignment, long comments). It can optionally
insert placeholder explanatory comments for isolated code chunks, but that is
opt-in because such comments should ideally be written by a human.
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import shutil
import subprocess
import sys
import tokenize
import tomllib
from pathlib import Path
from typing import Any

# Exact class panel required by the validator.
CLASS_PANEL = [
    "#==================#",
    "# Class Definition #",
    "#==================#",
]

# Allowed function/method lead-comment prefixes. Must stay in sync with code_validator.py.
FUNCTION_COMMENT_PREFIXES = (
    "# Function: ",
    "# Method: ",
    "# Helper Function: ",
    "# Helper Method: ",
    "# Internal Function: ",
    "# Internal Method: ",
    "# Public Function: ",
    "# Public Method: ",
)

# Maximum comment line length. Must match MAX_COMMENT_LENGTH in code_validator.py so
# that fixer output always passes validation.
MAX_COMMENT_LENGTH = 128
PROJECT_NAME = "graphregistry"


def _rich_print(message: str) -> None:
    """Print without requiring rich."""
    print(message)


def _get_project_info(path: Path) -> tuple[Path, str]:
    """Locate the nearest pyproject.toml and read [project].name."""
    pyproject_path = next(
        (
            parent / "pyproject.toml"
            for parent in path.resolve().parents
            if (parent / "pyproject.toml").exists()
        ),
        None,
    )
    if pyproject_path is None:
        raise RuntimeError(f"pyproject.toml not found for {path}")
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    name = data.get("project", {}).get("name")
    if not name:
        raise RuntimeError("[project].name missing from pyproject.toml")
    return pyproject_path.parent, name


def _expected_header(path: Path, root: Path, project_name: str) -> str:
    """Build the expected first-line header for a file."""
    local = path.resolve().relative_to(root)
    if local.parts[0] != project_name:
        local = Path(project_name) / local
    return f"# {local.as_posix()}"


def _is_blank(line: str) -> bool:
    return line.strip() == ""


def _is_import_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("import ") or stripped.startswith("from ")


def _indentation(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def fix_header(lines: list[str], path: Path, root: Path, project_name: str) -> list[str]:
    """Ensure the first line is the project-root-relative path comment."""
    if not lines:
        return lines
    expected = _expected_header(path, root, project_name)
    if lines[0] != expected:
        lines = [expected, *lines[1:]]
    return lines


def _first_def_or_class_index(lines: list[str]) -> int | None:
    """Return the index of the first top-level def or class, if any."""
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            return i
    return None


def fix_import_block(lines: list[str], project_name: str) -> list[str]:
    """Remove blank lines inside the initial import block and keep local imports last."""
    if not lines:
        return lines

    # Locate the first module-level import line. If a class or def appears
    # before any import, there is no import block to fix.
    first_import = next(
        (i for i, line in enumerate(lines) if _is_import_line(line)), None
    )
    if first_import is None:
        return lines

    first_def_or_class = _first_def_or_class_index(lines)
    if first_def_or_class is not None and first_import > first_def_or_class:
        return lines

    # Expand backward over any immediately preceding blank lines.
    start = first_import
    while start > 1 and _is_blank(lines[start - 1]):
        start -= 1

    # Expand forward over import lines and the blanks that separate them.
    end = start
    while end < len(lines) and (
        _is_import_line(lines[end]) or _is_blank(lines[end])
    ):
        end += 1

    import_lines = [line for line in lines[start:end] if _is_import_line(line)]
    if not import_lines:
        return lines

    non_local = []
    local = []
    for line in import_lines:
        stripped = line.strip()
        if stripped.startswith(f"import {project_name}") or stripped.startswith(
            f"from {project_name}"
        ):
            local.append(line)
        else:
            non_local.append(line)

    # Keep non-local order, sort local imports alphabetically.
    local_sorted = sorted(local)
    new_import_lines = non_local + local_sorted

    # Preserve a single trailing blank line after the import block if the
    # original file had one and the next line is real code.
    trailing_blank = end > start and _is_blank(lines[end - 1])

    rebuilt = list(lines[:start])
    rebuilt.extend(new_import_lines)
    if trailing_blank and end < len(lines) and not _is_blank(lines[end]):
        rebuilt.append("")
    rebuilt.extend(lines[end:])
    return rebuilt


def collapse_blank_lines(lines: list[str]) -> list[str]:
    """Collapse runs of blank lines to a single blank line."""
    result: list[str] = []
    in_blank_run = False
    for line in lines:
        if _is_blank(line):
            if not in_blank_run:
                result.append("")
                in_blank_run = True
        else:
            result.append(line)
            in_blank_run = False
    return result


def _looks_like_class_panel(prev_three: list[str]) -> bool:
    if len(prev_three) != 3:
        return False
    return all(line.strip().startswith("#") for line in prev_three) and any(
        "Class Definition" in line for line in prev_three
    )


def fix_class_panels(lines: list[str]) -> list[str]:
    """Ensure every class definition is preceded by the required panel."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("class "):
            # Panels carry the indentation of their class so nested classes get
            # properly indented panels, which the validator accepts.
            indent = _indentation(line)
            # Check whether the previous three lines form a class panel.
            if i >= 3 and _looks_like_class_panel(result[-3:]):
                # Replace the existing panel with the exact template, re-indented.
                result[-3:] = [indent + panel_line for panel_line in CLASS_PANEL]
            else:
                # Insert a panel. Make sure there is a blank line before it
                # when it is not at the very start of the file.
                if result and not _is_blank(result[-1]):
                    result.append("")
                result.extend(indent + panel_line for panel_line in CLASS_PANEL)
            result.append(line)
            i += 1
        else:
            result.append(line)
            i += 1
    return result


def _def_name(line: str) -> str | None:
    """Extract the function/method name from a 'def ...' or 'async def ...' line."""
    match = re.match(r"\s*(?:async\s+)?def\s+(\w+)", line)
    return match.group(1) if match else None


def _is_internal_def(line: str) -> bool:
    name = _def_name(line)
    return name is not None and name.startswith("_") and not name.startswith("__")


def _is_public_def(line: str) -> bool:
    name = _def_name(line)
    return name is not None and not name.startswith("_")


def _docstring_summary(lines: list[str], idx: int) -> str | None:
    """Return a short summary from the docstring following a def, if any."""
    if idx >= len(lines):
        return None
    next_line = lines[idx].lstrip()
    if not (next_line.startswith('"""') or next_line.startswith("'''")):
        return None
    # Single-line docstring.
    if (
        next_line.startswith('"""')
        and next_line.rstrip().endswith('"""')
        and next_line.count('"""') >= 2
    ) or (
        next_line.startswith("'''")
        and next_line.rstrip().endswith("'''")
        and next_line.count("'''") >= 2
    ):
        text = next_line.strip().strip('"').strip("'")
        return text.split(".")[0].strip()
    # Multi-line docstring: take the first non-empty content line.
    quote = '"""' if next_line.startswith('"""') else "'''"
    j = idx
    while j < len(lines):
        stripped = lines[j].lstrip()
        if stripped.count(quote) >= 2:
            inner = stripped.strip().strip('"').strip("'")
            return inner.split(".")[0].strip()
        if stripped and not stripped.startswith(quote):
            return stripped.strip(".").strip()
        j += 1
    return None


def _humanize(name: str) -> str:
    """Turn a snake_case name into a short phrase."""
    return name.replace("_", " ").strip()


def _make_lead_comment(prefix: str, name: str, summary: str | None) -> str:
    """Build a lead comment that fits within the line limit."""
    if summary:
        body = summary
    else:
        body = _humanize(name)
        if not body:
            body = "..."
    comment = f"{prefix} {body}"
    # Trim aggressively if somehow too long.
    if len(comment) > MAX_COMMENT_LENGTH:
        available = MAX_COMMENT_LENGTH - len(prefix) - len(" ...")
        comment = f"{prefix} {body[:available].rsplit(' ', 1)[0]}..."
    return comment


def fix_method_function_comments(lines: list[str]) -> list[str]:
    """Add missing lead comments only when a meaningful description can be derived from the docstring.

    The fixer never emits low-IQ comments that merely restate the function name.
    Functions without docstrings are left for human review in the LLM-fix cycle.
    """
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_import_line(line) or line.strip().startswith("class "):
            result.append(line)
            i += 1
            continue

        name = _def_name(line)
        if name is None:
            result.append(line)
            i += 1
            continue

        # Walk back over decorators in the *result* list.
        decorators: list[str] = []
        k = len(result) - 1
        while k >= 0 and result[k].lstrip().startswith("@"):
            decorators.insert(0, result[k])
            k -= 1

        # Walk back over the whole contiguous comment block, mirroring the validator:
        # a tagged line anywhere in the block counts as an existing lead comment, so
        # multi-line lead comments are never duplicated.
        block_end = k
        while block_end >= 0 and result[block_end].lstrip().startswith("#"):
            block_end -= 1
        comment_block = result[block_end + 1 : k + 1]
        has_prefix = any(
            comment_line.lstrip().startswith(FUNCTION_COMMENT_PREFIXES)
            for comment_line in comment_block
        )

        if not has_prefix:
            summary = _docstring_summary(lines, i + 1)
            if summary is None:
                # No docstring available to derive a meaningful comment; leave for LLM fix.
                result.append(line)
                i += 1
                continue
            if _is_internal_def(line):
                prefix = "# Internal Function:"
            elif _is_public_def(line):
                prefix = "# Public Method:"
            else:
                # Dunder or otherwise -- skip.
                result.append(line)
                i += 1
                continue
            comment = _indentation(line) + _make_lead_comment(prefix, name, summary)
            # Insert before the first decorator, if any.
            insert_at = len(result) - len(decorators)
            result.insert(insert_at, comment)

        result.append(line)
        i += 1
    return result


def fix_comment_prefixes(lines: list[str]) -> list[str]:
    """Normalize old-style function/method lead comments based on the target def."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        if stripped.startswith("# Function: ") or stripped.startswith("# Method: "):
            old_prefix = (
                "# Function: "
                if stripped.startswith("# Function: ")
                else "# Method: "
            )
            # Find the target definition, skipping decorators, blank lines, and
            # continuation comment lines of multi-line lead comments.
            j = i + 1
            while j < len(lines) and (
                lines[j].lstrip().startswith("@")
                or _is_blank(lines[j])
                or lines[j].lstrip().startswith("#")
            ):
                j += 1
            target = lines[j] if j < len(lines) else ""
            if _is_public_def(target):
                new_prefix = "# Public Method:"
            else:
                new_prefix = "# Internal Function:"
            line = line.replace(old_prefix, new_prefix + " ", 1)
            # Ensure the converted lead comment still fits the line limit.
            if len(line) > MAX_COMMENT_LENGTH:
                indent = _indentation(line)
                description = line.lstrip()[len(new_prefix) + 1 :].strip()
                line = indent + _make_lead_comment(new_prefix, "", description)
        result.append(line)
        i += 1
    return result


def _wrap_comment(line: str, max_len: int = MAX_COMMENT_LENGTH) -> list[str]:
    """Split a comment line into multiple lines under max_len."""
    indent = _indentation(line)
    prefix = "# "
    content = line.lstrip()[2:]  # drop '# '
    if len(line) <= max_len:
        return [line]

    wrapped: list[str] = []
    while content:
        # Available space for content on a continuation line.
        available = max_len - len(indent) - len(prefix)
        if available <= 0:
            # Degenerate indentation; just return original.
            return [line]
        if len(content) <= available:
            wrapped.append(indent + prefix + content)
            break
        # Prefer splitting at a space.
        cut = content.rfind(" ", 0, available + 1)
        if cut <= 0:
            # Force split at available width.
            cut = available
        wrapped.append(indent + prefix + content[:cut].rstrip())
        content = content[cut:].lstrip()
    return wrapped


def fix_long_comments(lines: list[str]) -> list[str]:
    """Split comment lines that exceed the maximum length."""
    result: list[str] = []
    for line in lines:
        if line.lstrip().startswith("#") and len(line) > MAX_COMMENT_LENGTH:
            result.extend(_wrap_comment(line))
        else:
            result.append(line)
    return result


def _extract_lead_description(line: str) -> str:
    """Return the description part of an existing lead comment."""
    stripped = line.lstrip()
    for prefix in ("# Internal Function:", "# Public Method:"):
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def collapse_lead_comment_panels(lines: list[str]) -> list[str]:
    """Collapse lead-comment blocks that contain duplicate tags.

    The validator accepts multi-line lead-comment blocks as long as at least one
    line carries a type tag, so blocks with a single tag are left untouched
    (including their continuation lines and decorative borders). This pass only
    rewrites blocks that contain more than one tagged line, keeping the last one.
    """
    # Find all def lines (bottom-up so index changes are safe).
    def_indices = [
        i
        for i, line in enumerate(lines)
        if _def_name(line) is not None
    ]

    for def_idx in reversed(def_indices):
        name = _def_name(lines[def_idx])
        if name is None or (name.startswith("_") and name.startswith("__")):
            continue

        expected_prefix = (
            "# Public Method:" if _is_public_def(lines[def_idx]) else "# Internal Function:"
        )

        # Walk backwards over decorators and comments to collect the comment
        # block that immediately precedes the definition.
        i = def_idx - 1
        while i >= 0 and lines[i].lstrip().startswith("@"):
            i -= 1
        block_end = i
        block_start = block_end
        while block_start >= 0 and lines[block_start].lstrip().startswith("#"):
            block_start -= 1
        block_start += 1

        if block_start > block_end:
            continue

        block = lines[block_start : block_end + 1]
        lead_positions = [
            j
            for j, line in enumerate(block)
            if line.lstrip().startswith("# Internal Function:")
            or line.lstrip().startswith("# Public Method:")
        ]
        # A single tagged line already satisfies the validator; leave the block
        # (and its continuation lines) exactly as written.
        if len(lead_positions) < 2:
            continue

        # Use the last lead comment found; remove any borders/duplicates.
        chosen = block[lead_positions[-1]]
        description = _extract_lead_description(chosen)
        indent = _indentation(chosen)
        new_comment = indent + _make_lead_comment(expected_prefix, name, description or None)
        lines[block_start : block_end + 1] = [new_comment]

    return lines


def fix_keyword_alignment(lines: list[str]) -> list[str]:
    """Vertically align '=' signs in multi-line keyword-argument groups."""
    text = "\n".join(lines)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return lines

    # Collect groups of consecutive keyword arguments on consecutive lines.
    replacements: dict[int, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        keywords = [
            kw
            for kw in node.keywords
            if kw.arg is not None and hasattr(kw, "lineno")
        ]
        if len(keywords) < 2:
            continue

        groups: list[list[ast.keyword]] = []
        current: list[ast.keyword] = []
        for kw in keywords:
            if current and kw.lineno != current[-1].lineno + 1:
                if len(current) >= 2:
                    groups.append(current)
                current = []
            current.append(kw)
        if len(current) >= 2:
            groups.append(current)

        for group in groups:
            group_lines = [lines[kw.lineno - 1] for kw in group]
            equal_columns = [line.index("=") for line in group_lines]
            if len(set(equal_columns)) == 1:
                # Already aligned; leave it alone to avoid unnecessary diffs.
                continue
            max_len = max(len(kw.arg) for kw in group)
            for kw in group:
                idx = kw.lineno - 1
                original = lines[idx]
                indent = _indentation(original)
                arg = kw.arg
                # Find the '=' that follows the argument name.
                search_start = len(indent) + len(arg)
                eq_pos = original.find("=", search_start)
                if eq_pos == -1:
                    continue
                value = original[eq_pos + 1 :].lstrip()
                new_line = f"{indent}{arg.ljust(max_len)} = {value}"
                replacements[idx] = new_line

    if not replacements:
        return lines

    result = list(lines)
    for idx, new_line in replacements.items():
        result[idx] = new_line
    return result


def fix_dict_alignment(lines: list[str]) -> list[str]:
    """Vertically align ':' separators in multi-line dictionary literals."""
    text = "\n".join(lines)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return lines

    replacements: dict[int, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        entries: list[tuple[ast.Constant, int]] = []
        for key in node.keys:
            if key is None:
                continue
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            if key.lineno != key.end_lineno:
                continue
            entries.append((key, key.lineno - 1))

        if len(entries) < 2:
            continue

        groups: list[list[tuple[ast.Constant, int]]] = []
        current: list[tuple[ast.Constant, int]] = []
        for key, idx in entries:
            if current and idx != current[-1][1] + 1:
                if len(current) >= 2:
                    groups.append(current)
                current = []
            current.append((key, idx))
        if len(current) >= 2:
            groups.append(current)

        for group in groups:
            colon_columns = []
            for key, idx in group:
                original = lines[idx]
                colon_pos = original.find(":", key.end_col_offset)
                if colon_pos == -1:
                    break
                colon_columns.append(colon_pos)
            if len(colon_columns) != len(group) or len(set(colon_columns)) == 1:
                # Already aligned or cannot determine; leave it alone.
                continue
            max_width = max(key.end_col_offset - key.col_offset for key, _ in group)
            for key, idx in group:
                original = lines[idx]
                indent = original[: key.col_offset]
                key_text = original[key.col_offset : key.end_col_offset]
                colon_pos = original.find(":", key.end_col_offset)
                if colon_pos == -1:
                    continue
                value_text = original[colon_pos + 1 :].lstrip()
                new_line = f"{indent}{key_text.ljust(max_width)} : {value_text}"
                replacements[idx] = new_line

    if not replacements:
        return lines

    result = list(lines)
    for idx, new_line in replacements.items():
        result[idx] = new_line
    return result


def _multiline_string_lines(text: str) -> set[int]:
    """Return 0-based line indices occupied by multi-line strings."""
    lines: set[int] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for tok in tokens:
            if tok.type == tokenize.STRING and tok.start[0] != tok.end[0]:
                lines.update(range(tok.start[0] - 1, tok.end[0]))
    except tokenize.TokenizeError:
        pass
    return lines


def _guess_chunk_comment(first_line: str) -> str | None:
    """Generate a conservative explanatory comment for a code chunk."""
    stripped = first_line.strip()
    if stripped.startswith("import ") or stripped.startswith("from "):
        return "# Import the required modules."
    if stripped.startswith("@") and not stripped.startswith("@pytest"):
        return "# Apply the decorator to the following definition."
    if stripped.startswith("return"):
        return "# Return the computed result."
    if stripped.startswith("if "):
        return "# Handle the conditional case."
    if stripped.startswith("for "):
        return "# Iterate over the collection."
    if stripped.startswith("while "):
        return "# Loop until the condition is met."
    if stripped.startswith("try:"):
        return "# Execute the operation and handle errors."
    if stripped.startswith("with "):
        return "# Manage the resource context."
    if stripped.startswith("raise "):
        return "# Raise the encountered error."

    assignment = re.match(r"(\w+)\s*[=:]\s*", stripped)
    if assignment:
        name = assignment.group(1)
        if stripped.startswith(f"{name}:"):
            return f"# Declare the {name} data structure."
        return f"# Prepare {name} for the following steps."

    call = re.match(r"(\w+)\s*\(", stripped)
    if call:
        return f"# Invoke {call.group(1)}."

    return "# Continue with the next step."


def fix_code_chunks(lines: list[str]) -> list[str]:
    """Add explanatory comments before code chunks separated by blank lines.

    This transform is intentionally conservative: it only adds a comment when
    the first line of a chunk is a simple statement and the chunk is not
    already introduced by a comment, class panel, or method/function lead
    comment.
    """
    text = "\n".join(lines)
    multiline = _multiline_string_lines(text)

    # Split into chunks separated by blank lines, ignoring multiline strings.
    chunks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if idx in multiline:
            continue
        if _is_blank(line):
            if current:
                chunks.append(current)
                current = []
        else:
            current.append((idx, line))
    if current:
        chunks.append(current)

    # Determine which chunks need a leading comment.
    insertions: dict[int, str] = {}
    for chunk in chunks:
        first_idx, first_line = chunk[0]
        # Already commented or part of a panel/lead comment?
        if first_line.lstrip().startswith("#"):
            continue
        # Function/method lead comments are added separately; don't duplicate.
        if first_idx > 0:
            prev = lines[first_idx - 1].lstrip()
            if prev.startswith("# Internal Function: ") or prev.startswith(
                "# Public Method: "
            ):
                continue
        # Don't add comments before class panels (handled elsewhere).
        if first_line.lstrip().startswith("class "):
            continue
        # Skip import lines; the import-block fixer should make them contiguous.
        if _is_import_line(first_line):
            continue
        comment = _guess_chunk_comment(first_line)
        if comment:
            indent = _indentation(first_line)
            insertions[first_idx] = indent + comment

    if not insertions:
        return lines

    result: list[str] = []
    for idx, line in enumerate(lines):
        if idx in insertions:
            result.append(insertions[idx])
        result.append(line)
    return result


def _parse_syntax(lines: list[str], path: Path) -> bool:
    """Return True if the lines form valid Python syntax."""
    text = "\n".join(lines)
    try:
        ast.parse(text)
        return True
    except SyntaxError as exc:
        _rich_print(f"  ⚠️  Syntax error introduced in {path}: {exc}")
        return False


def _count_changes(original: list[str], fixed: list[str]) -> int:
    """Rough change count by differing lines."""
    import difflib

    diff = list(difflib.unified_diff(original, fixed, lineterm=""))
    # Count added/removed lines, ignoring header.
    return sum(1 for line in diff if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))


def fix_file(
    path: Path,
    root: Path,
    project_name: str,
    add_chunk_comments: bool = False,
) -> tuple[list[str] | None, dict[str, Any]]:
    """Apply all safe fixes to a file and return the new lines plus a summary."""
    text = path.read_text(encoding="utf-8")
    original_lines = text.splitlines()
    lines = list(original_lines)
    summary: dict[str, Any] = {"path": path, "changed": 0, "error": None}

    try:
        lines = fix_header(lines, path, root, project_name)
        lines = fix_import_block(lines, project_name)
        lines = collapse_blank_lines(lines)
        lines = fix_class_panels(lines)
        lines = fix_comment_prefixes(lines)
        lines = fix_method_function_comments(lines)
        lines = fix_long_comments(lines)
        lines = collapse_lead_comment_panels(lines)
        lines = fix_keyword_alignment(lines)
        lines = fix_dict_alignment(lines)
        if add_chunk_comments:
            lines = fix_code_chunks(lines)
        # A second pass catches any long comments introduced by alignment.
        lines = fix_long_comments(lines)
    except Exception as exc:
        summary["error"] = f"fixer exception: {exc}"
        return None, summary

    if not _parse_syntax(lines, path):
        summary["error"] = "syntax check failed after fixes"
        return None, summary

    summary["changed"] = _count_changes(original_lines, lines)
    return lines, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply mechanical code-structure fixes to Python files."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="Files or directories to fix")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write fixes in place (default is dry-run).",
    )
    parser.add_argument(
        "--add-chunk-comments",
        action="store_true",
        help="Insert placeholder comments before isolated code chunks.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run code_validator.py on each file after writing.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak backups when writing.",
    )
    args = parser.parse_args(argv)

    # Resolve files.
    files: list[Path] = []
    for p in args.paths:
        if p.is_dir():
            files.extend(sorted(p.rglob("*.py")))
        elif p.suffix == ".py":
            files.append(p)
        else:
            _rich_print(f"Skipping non-Python path: {p}")

    if not files:
        _rich_print("No Python files found.")
        return 0

    # Project root/name from the first file.
    try:
        root, project_name = _get_project_info(files[0])
    except RuntimeError as exc:
        _rich_print(f"Error: {exc}")
        return 1

    changed_files = 0
    failed_files = 0
    validator_path = Path(__file__).with_name("code_validator.py")

    for path in files:
        _rich_print(f"Processing {path} ...")
        lines, summary = fix_file(
            path,
            root,
            project_name,
            add_chunk_comments=args.add_chunk_comments,
        )
        if summary.get("error"):
            _rich_print(f"  ❌ {summary['error']}")
            failed_files += 1
            continue

        if lines is None:
            failed_files += 1
            continue

        changes = summary["changed"]
        if changes == 0:
            _rich_print("  ✅ No changes needed.")
            continue

        if not args.write:
            _rich_print(f"  📝 Would apply ~{changes} line changes (dry-run).")
            continue

        # Write with optional backup.
        if not args.no_backup:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.write_text("\n".join(lines) + ("\n" if lines and lines[-1] else ""), encoding="utf-8")
        changed_files += 1
        _rich_print(f"  ✅ Applied ~{changes} line changes.")

        if args.check and validator_path.exists():
            result = subprocess.run(
                [sys.executable, str(validator_path), str(path)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or "FAILED" in result.stdout:
                _rich_print(f"  ⚠️  Validation still reports issues:\n{result.stdout}")
            else:
                _rich_print(f"  ✅ Validation passed.")

    _rich_print(
        f"\nSummary: {changed_files} file(s) changed, {failed_files} failure(s), {len(files)} file(s) processed."
    )
    return 1 if failed_files else 0


if __name__ == "__main__":
    raise SystemExit(main())
