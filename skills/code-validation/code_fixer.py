# graphregistry/.opencode/skills/code-validation/code_fixer.py
"""Mechanical fixer for the project's code-structure conventions.

This script applies deterministic textual fixes that mirror the checks performed
by ``code_validator.py``. It is intentionally conservative:

* It never reorders imports, which can have initialization side effects.
* It excludes multiline-string contents from textual rewrites and verifies that
  string literal values remain unchanged.
* It validates the resulting file with ``ast.parse`` before writing.
* It runs in dry-run mode with a unified diff by default; use ``--write`` to persist changes.
* It backs up modified files in place with a ``.bak`` suffix when writing.

The fixer handles mechanical rules (headers, blank lines, exact class panels,
existing-comment normalization and wrapping, and keyword/dict alignment). It
never invents explanatory narratives; missing comments require an author.
"""

from __future__ import annotations

import argparse
import ast
import difflib
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

# Maximum comment line length. Must match MAX_COMMENT_LENGTH in code_validator.py so
# that fixer output always passes validation.
MAX_COMMENT_LENGTH = 128
CANONICAL_FUNCTION_COMMENT_PREFIXES = (
    "# Internal Function:",
    "# Internal Method:",
    "# Public Function:",
    "# Public Method:",
)
NORMALIZED_FUNCTION_COMMENT_PREFIXES = (
    "# Function:",
    "# Method:",
    *CANONICAL_FUNCTION_COMMENT_PREFIXES,
)


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
    if not lines or 0 in _multiline_string_lines("\n".join(lines)):
        return lines
    expected = _expected_header(path, root, project_name)
    if lines[0] != expected:
        lines = [expected, *lines[1:]]
    return lines


def _first_def_or_class_index(
    lines: list[str], ignored_lines: set[int] | None = None
) -> int | None:
    """Return the first textual def or class outside multiline strings."""
    ignored = ignored_lines or set()
    for i, line in enumerate(lines):
        if i in ignored:
            continue
        stripped = line.lstrip()
        if (
            stripped.startswith("def ")
            or stripped.startswith("async def ")
            or stripped.startswith("class ")
        ):
            return i
    return None


def fix_import_block(lines: list[str], project_name: str = "") -> list[str]:
    """Remove import-block blanks without reordering; retain the legacy signature."""
    if not lines:
        return lines

    multiline = _multiline_string_lines("\n".join(lines))

    # Locate the first module-level import line. If a class or def appears
    # before any import, there is no import block to fix.
    first_import = next(
        (
            i
            for i, line in enumerate(lines)
            if i not in multiline and _is_import_line(line)
        ),
        None,
    )
    if first_import is None:
        return lines

    first_def_or_class = _first_def_or_class_index(lines, multiline)
    if first_def_or_class is not None and first_import > first_def_or_class:
        return lines

    # Expand backward over any immediately preceding blank lines.
    start = first_import
    while (
        start > 1
        and start - 1 not in multiline
        and _is_blank(lines[start - 1])
    ):
        start -= 1

    # Expand forward over import lines and the blanks that separate them.
    end = start
    while end < len(lines) and end not in multiline and (
        _is_import_line(lines[end]) or _is_blank(lines[end])
    ):
        end += 1

    import_lines = [
        line
        for idx, line in enumerate(lines[start:end], start=start)
        if idx not in multiline and _is_import_line(line)
    ]
    if not import_lines:
        return lines

    # Preserve the original sequence: imports can have initialization side effects.
    trailing_blank = end > start and end - 1 not in multiline and _is_blank(lines[end - 1])
    rebuilt = list(lines[:start])
    rebuilt.extend(import_lines)
    if trailing_blank and end < len(lines) and not _is_blank(lines[end]):
        rebuilt.append("")
    rebuilt.extend(lines[end:])
    return rebuilt


def collapse_blank_lines(lines: list[str]) -> list[str]:
    """Collapse blank runs outside multiline strings to a single blank line."""
    multiline = _multiline_string_lines("\n".join(lines))
    result: list[str] = []
    in_blank_run = False
    for idx, line in enumerate(lines):
        if idx in multiline:
            result.append(line)
            in_blank_run = False
        elif _is_blank(line):
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
    """Place exact structural panels before each class's first decorator."""
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return lines

    multiline = _multiline_string_lines("\n".join(lines))
    class_nodes = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)),
        key=lambda node: node.lineno,
        reverse=True,
    )
    result = list(lines)
    for node in class_nodes:
        class_idx = node.lineno - 1
        anchor_idx = (
            min(decorator.lineno for decorator in node.decorator_list) - 1
            if node.decorator_list
            else class_idx
        )
        indent = _indentation(lines[class_idx])
        panel = [indent + panel_line for panel_line in CLASS_PANEL]

        # Older fixer versions put panels after decorators. Remove only a direct,
        # recognizable three-line panel so unrelated decorator comments survive.
        misplaced_start = class_idx - 3
        if (
            node.decorator_list
            and misplaced_start >= anchor_idx
            and not any(
                idx in multiline
                for idx in range(misplaced_start, class_idx)
            )
            and _looks_like_class_panel(lines[misplaced_start:class_idx])
        ):
            del result[misplaced_start:class_idx]

        # Recognize an existing panel before the first decorator, or insert the
        # structural panel without adding any class-story narrative.
        panel_start = anchor_idx - 3
        if (
            panel_start >= 0
            and not any(
                idx in multiline for idx in range(panel_start, anchor_idx)
            )
            and _looks_like_class_panel(lines[panel_start:anchor_idx])
        ):
            result[panel_start:anchor_idx] = panel
            continue

        insertion = panel
        if (
            anchor_idx > 0
            and not _is_blank(result[anchor_idx - 1])
            and not result[anchor_idx - 1].lstrip().startswith("#")
        ):
            insertion = ["", *panel]
        result[anchor_idx:anchor_idx] = insertion
    return result


def _definition_comment_targets(lines: list[str]) -> dict[int, tuple[str, int]]:
    """Map definitions to canonical existing-comment tags and decorator anchors."""
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return {}

    targets: dict[int, tuple[str, int]] = {}

    class DefinitionVisitor(ast.NodeVisitor):
        """Track whether each definition is directly in class scope."""

        def __init__(self) -> None:
            self.in_class = False

        def _visit_function(
            self, node: ast.FunctionDef | ast.AsyncFunctionDef
        ) -> None:
            is_dunder = (
                node.name.startswith("__")
                and node.name.endswith("__")
                and len(node.name) >= 4
            )
            visibility = (
                "Public" if is_dunder or not node.name.startswith("_") else "Internal"
            )
            definition_kind = "Method" if self.in_class else "Function"
            anchor_idx = (
                min(decorator.lineno for decorator in node.decorator_list) - 1
                if node.decorator_list
                else node.lineno - 1
            )
            targets[node.lineno - 1] = (
                f"# {visibility} {definition_kind}:",
                anchor_idx,
            )
            outer_class = self.in_class
            self.in_class = False
            self.generic_visit(node)
            self.in_class = outer_class

        visit_FunctionDef = _visit_function
        visit_AsyncFunctionDef = _visit_function

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            outer_class = self.in_class
            self.in_class = True
            for statement in node.body:
                self.visit(statement)
            self.in_class = outer_class

    visitor = DefinitionVisitor()
    for statement in tree.body:
        visitor.visit(statement)
    return targets


def _lead_comment_prefix(line: str) -> str | None:
    """Return a generic or canonical lead tag without its narrative."""
    stripped = line.lstrip()
    return next(
        (
            prefix
            for prefix in NORMALIZED_FUNCTION_COMMENT_PREFIXES
            if stripped.startswith(prefix)
        ),
        None,
    )


def fix_comment_prefixes(lines: list[str]) -> list[str]:
    """Normalize only existing generic or wrong-scope tags by AST scope."""
    multiline = _multiline_string_lines("\n".join(lines))
    targets = _definition_comment_targets(lines)
    result = list(lines)
    for expected_prefix, anchor_idx in targets.values():
        block_start = anchor_idx - 1
        while (
            block_start >= 0
            and block_start not in multiline
            and lines[block_start].lstrip().startswith("#")
        ):
            block_start -= 1

        for comment_idx in range(block_start + 1, anchor_idx):
            old_prefix = _lead_comment_prefix(lines[comment_idx])
            if old_prefix is None or old_prefix == expected_prefix:
                continue
            line = result[comment_idx]
            description = line.lstrip()[len(old_prefix) :].strip()
            replacement = expected_prefix
            if description:
                replacement = f"{replacement} {description}"
            result[comment_idx] = _indentation(line) + replacement
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
    """Split long comment lines outside multiline strings."""
    multiline = _multiline_string_lines("\n".join(lines))
    result: list[str] = []
    for idx, line in enumerate(lines):
        if (
            idx not in multiline
            and line.lstrip().startswith("#")
            and len(line) > MAX_COMMENT_LENGTH
        ):
            result.extend(_wrap_comment(line))
        else:
            result.append(line)
    return result


def _apply_single_line_replacements(
    lines: list[str],
    replacement_groups: list[list[tuple[int, int, int, str]]],
) -> list[str]:
    """Apply exact line-local edits, rejecting groups that compete for a line."""
    usable_groups: list[list[tuple[int, int, int, str]]] = []
    for replacements in replacement_groups:
        line_indices = [idx for idx, _, _, _ in replacements]
        if len(line_indices) != len(set(line_indices)):
            continue
        changed: list[tuple[int, int, int, str]] = []
        for idx, start, end, replacement in replacements:
            updated = lines[idx][:start] + replacement + lines[idx][end:]
            if updated != lines[idx]:
                changed.append((idx, start, end, replacement))
        if changed:
            usable_groups.append(changed)

    line_use_count: dict[int, int] = {}
    for replacements in usable_groups:
        for idx, _, _, _ in replacements:
            line_use_count[idx] = line_use_count.get(idx, 0) + 1

    result = list(lines)
    for replacements in usable_groups:
        if any(line_use_count[idx] > 1 for idx, _, _, _ in replacements):
            continue
        for idx, start, end, replacement in replacements:
            result[idx] = result[idx][:start] + replacement + result[idx][end:]
    return result


def fix_keyword_alignment(lines: list[str]) -> list[str]:
    """Align only unambiguous '=' separators on single-line keyword entries."""
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return lines

    replacement_groups: list[list[tuple[int, int, int, str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        keywords = [kw for kw in node.keywords if kw.arg is not None]
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
            parsed: list[tuple[int, str, int, int]] = []
            for kw in group:
                if kw.arg is None or kw.lineno != kw.end_lineno:
                    break
                if (
                    kw.value.lineno != kw.value.end_lineno
                    or kw.lineno != kw.value.lineno
                ):
                    break
                idx = kw.lineno - 1
                line = lines[idx]
                separator_start = kw.col_offset + len(kw.arg)
                if line[kw.col_offset:separator_start] != kw.arg:
                    break
                match = re.match(r"[ \t]*=[ \t]*", line[separator_start:])
                if match is None:
                    break
                parsed.append(
                    (idx, kw.arg, separator_start, separator_start + match.end())
                )
            if len(parsed) != len(group):
                continue

            max_len = max(len(arg) for _, arg, _, _ in parsed)
            replacements = [
                (
                    idx,
                    start,
                    end,
                    " " * (max_len - len(arg) + 1) + "= ",
                )
                for idx, arg, start, end in parsed
            ]
            replacement_groups.append(replacements)
    return _apply_single_line_replacements(lines, replacement_groups)


def fix_dict_alignment(lines: list[str]) -> list[str]:
    """Align only unambiguous ':' separators on single-line dictionary entries."""
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return lines

    replacement_groups: list[list[tuple[int, int, int, str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        entries: list[tuple[ast.Constant, int]] = []
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                continue
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            if (
                key.lineno != key.end_lineno
                or value.lineno != value.end_lineno
                or key.lineno != value.lineno
            ):
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
            parsed: list[tuple[int, int, int, int]] = []
            for key, idx in group:
                end_col_offset = key.end_col_offset
                if end_col_offset is None:
                    break
                line = lines[idx]
                match = re.match(r"[ \t]*:[ \t]*", line[end_col_offset:])
                if match is None:
                    break
                parsed.append(
                    (
                        idx,
                        end_col_offset - key.col_offset,
                        end_col_offset,
                        end_col_offset + match.end(),
                    )
                )
            if len(parsed) != len(group):
                continue

            max_width = max(width for _, width, _, _ in parsed)
            replacements = [
                (
                    idx,
                    start,
                    end,
                    " " * (max_width - width + 1) + ": ",
                )
                for idx, width, start, end in parsed
            ]
            replacement_groups.append(replacements)
    return _apply_single_line_replacements(lines, replacement_groups)


def _multiline_string_lines(text: str) -> set[int]:
    """Return multiline-string lines, or protect all lines if tokenization fails."""
    lines: set[int] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for tok in tokens:
            if tok.type == tokenize.STRING and tok.start[0] != tok.end[0]:
                lines.update(range(tok.start[0] - 1, tok.end[0]))
    except (tokenize.TokenError, SyntaxError):
        # Malformed or unterminated strings must not expose lookalike code to rewrites.
        return set(range(len(text.splitlines())))
    return lines


def _parse_syntax(lines: list[str], path: Path) -> bool:
    """Return True if the lines form valid Python syntax."""
    text = "\n".join(lines)
    try:
        ast.parse(text)
        return True
    except SyntaxError as exc:
        _rich_print(f"  ⚠️  Syntax error introduced in {path}: {exc}")
        return False


def _unified_diff(path: Path, original: list[str], fixed: list[str]) -> str:
    """Return a reviewable unified diff without writing either version."""
    return "\n".join(
        difflib.unified_diff(
            original,
            fixed,
            fromfile=str(path),
            tofile=f"{path} (fixed)",
            lineterm="",
        )
    )


def _count_changes(original: list[str], fixed: list[str]) -> int:
    """Rough change count by differing lines."""
    diff = list(difflib.unified_diff(original, fixed, lineterm=""))
    # Count added/removed lines, ignoring header.
    return sum(
        1
        for line in diff
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )


def _string_literal_values(lines: list[str]) -> list[str]:
    """Return every parsed string value in stable AST traversal order."""
    return [
        node.value
        for node in ast.walk(ast.parse("\n".join(lines)))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def fix_file(
    path: Path,
    root: Path,
    project_name: str,
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
        lines = fix_long_comments(lines)
        lines = fix_keyword_alignment(lines)
        lines = fix_dict_alignment(lines)
        # A second pass catches any long comments introduced by alignment.
        lines = fix_long_comments(lines)
    except Exception as exc:
        summary["error"] = f"fixer exception: {exc}"
        return None, summary

    if not _parse_syntax(lines, path):
        summary["error"] = "syntax check failed after fixes"
        return None, summary

    # Formatting must never mutate literal data, even if a future pass regresses.
    try:
        original_strings = _string_literal_values(original_lines)
        fixed_strings = _string_literal_values(lines)
    except SyntaxError as exc:
        summary["error"] = f"string literal safety check failed: {exc}"
        return None, summary
    if original_strings != fixed_strings:
        summary["error"] = "string literal values changed after fixes"
        return None, summary

    summary["changed"] = _count_changes(original_lines, lines)
    summary["diff"] = _unified_diff(path, original_lines, lines)
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

    changed_files = 0
    failed_files = 0
    validator_path = Path(__file__).with_name("code_validator.py")

    for path in files:
        _rich_print(f"Processing {path} ...")
        try:
            root, project_name = _get_project_info(path)
        except RuntimeError as exc:
            _rich_print(f"  ❌ {exc}")
            failed_files += 1
            continue
        lines, summary = fix_file(path, root, project_name)
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
            _rich_print(summary["diff"])
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
