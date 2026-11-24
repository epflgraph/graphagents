# graphagents/skills/code-validation/tests/test_code_fixer.py
import ast
from pathlib import Path
import sys
import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))
import code_fixer
import code_validator


def _make_project(tmp_path: Path, project_name: str) -> tuple[Path, Path]:
    """Create an isolated project and one Python fixture with an old header."""
    root = tmp_path / project_name
    root.mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{project_name}"\n', encoding="utf-8"
    )
    path = root / "sample.py"
    path.write_text("# old/header.py\nvalue = 1\n", encoding="utf-8")
    return root, path


def _assert_ast_equivalent(original: list[str], fixed: list[str]) -> None:
    """Prove formatting retained every parsed value and statement."""
    original_tree = ast.parse("\n".join(original))
    fixed_tree = ast.parse("\n".join(fixed))
    assert ast.dump(original_tree, include_attributes=False) == ast.dump(
        fixed_tree, include_attributes=False
    )


def test_collapse_blank_lines_preserves_runs_inside_multiline_strings() -> None:
    """Only blank runs in executable source should be collapsed."""
    lines = [
        'TEXT = """',
        "first",
        "",
        "",
        "last",
        '"""',
        "",
        "",
        "after = True",
    ]

    fixed = code_fixer.collapse_blank_lines(lines)

    assert fixed == [
        'TEXT = """',
        "first",
        "",
        "",
        "last",
        '"""',
        "",
        "after = True",
    ]


def test_tokenize_error_conservatively_protects_unterminated_multiline_string() -> None:
    """Tokenizer failures disable textual rewrites instead of exposing fake code."""
    lines = [
        'TEXT = """',
        "class Fake:",
        "    def fake_method(self):",
        "from fake.package import value",
        "",
        "",
        "# Function: " + "x" * 150,
    ]

    protected = code_fixer._multiline_string_lines("\n".join(lines))

    assert protected == set(range(len(lines)))
    assert code_fixer.collapse_blank_lines(lines) == lines
    assert code_fixer.fix_import_block(lines) == lines
    assert code_fixer.fix_class_panels(lines) == lines
    assert code_fixer.fix_long_comments(lines) == lines


def test_all_textual_fixes_ignore_fake_code_inside_multiline_strings(
    tmp_path: Path,
) -> None:
    """Class, def, import, and comment lookalikes remain literal string data."""
    root = tmp_path / "demo"
    root.mkdir()
    path = root / "sample.py"
    long_fake_comment = "# Function: " + "x" * 150
    lines = [
        "# demo/sample.py",
        'TEXT = """',
        "class Fake:",
        "    def fake_method(self):",
        "from fake.package import value",
        "",
        "",
        "    # Public Method: Fake narrative",
        long_fake_comment,
        '"""',
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    fixed, summary = code_fixer.fix_file(path, root, "demo")

    assert summary["error"] is None
    assert summary["changed"] == 0
    assert fixed == lines


def test_undocumented_definitions_never_receive_explanatory_comments(
    tmp_path: Path,
) -> None:
    """No definition visibility, scope, or async syntax triggers comment creation."""
    root = tmp_path / "demo"
    root.mkdir()
    path = root / "sample.py"
    lines = [
        "# demo/sample.py",
        "def public_function():",
        "    pass",
        "",
        "def _private_function():",
        "    pass",
        "",
        "def __module_dunder__():",
        "    pass",
        "",
        "async def async_function():",
        "    pass",
        "",
        "def outer():",
        "    def _nested_private():",
        "        pass",
        "",
        "    async def nested_public():",
        "        pass",
        "",
        "class Example:",
        "    def method(self):",
        "        pass",
        "",
        "    def _private_method(self):",
        "        pass",
        "",
        "    def __init__(self):",
        "        pass",
        "",
        "    async def _async_method(self):",
        "        pass",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    fixed, summary = code_fixer.fix_file(path, root, "demo")

    assert summary["error"] is None
    assert fixed == code_fixer.fix_class_panels(lines)
    comments = [
        line
        for line in fixed or []
        if line.lstrip().startswith("#")
        and line != "# demo/sample.py"
        and line.strip() not in code_fixer.CLASS_PANEL
    ]
    assert comments == []
    assert "TODO" not in "\n".join(fixed or [])
    for obsolete_api in (
        "fix_method_function_comments",
        "fix_code_chunks",
        "_guess_chunk_comment",
        "_make_lead_comment",
        "_humanize",
    ):
        assert not hasattr(code_fixer, obsolete_api)


def test_missing_narratives_still_fail_validation_after_fixing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mechanical fixing cannot satisfy or conceal missing narrative requirements."""
    root, path = _make_project(tmp_path, "demo")
    path.write_text(
        "# demo/sample.py\n\ndef undocumented():\n    pass\n",
        encoding="utf-8",
    )

    result = code_fixer.main(["--write", "--no-backup", str(path)])
    capsys.readouterr()
    validation_result = code_validator.main([str(path)])
    output = capsys.readouterr().out

    assert result == 0
    assert validation_result == code_validator.EXIT_VIOLATIONS == 1
    assert "Function/method definition" in output
    assert "descriptive comment" in output
    assert "TODO" not in path.read_text(encoding="utf-8")


def test_existing_lead_tags_normalize_by_ast_scope_without_new_narratives() -> None:
    """Only tags attached to existing descriptions are mechanically corrected."""
    lines = [
        "# Function: Existing asynchronous narrative.",
        "@register(",
        "    option=True,",
        ")",
        "async def decorated_top():",
        "    pass",
        "",
        "# Public Method: Existing private module narrative.",
        "def _private_module():",
        "    pass",
        "",
        "# Internal Function: Existing module dunder narrative.",
        "def __module_dunder__():",
        "    pass",
        "",
        "class Example:",
        "    # Public Function: Existing public method narrative.",
        "    def method(self):",
        "        pass",
        "",
        "    # Public Function: Existing private method narrative.",
        "    def _method(self):",
        "        pass",
        "",
        "    # Internal Function: Existing method dunder narrative.",
        "    def __init__(self):",
        "        pass",
        "",
        "# Internal Method: Existing outer narrative.",
        "def outer():",
        "    # Public Method: Existing nested private narrative.",
        "    def _nested():",
        "        pass",
    ]

    fixed = code_fixer.fix_comment_prefixes(lines)

    assert len(fixed) == len(lines)
    for expected in (
        "# Public Function: Existing asynchronous narrative.",
        "# Internal Function: Existing private module narrative.",
        "# Public Function: Existing module dunder narrative.",
        "    # Public Method: Existing public method narrative.",
        "    # Internal Method: Existing private method narrative.",
        "    # Public Method: Existing method dunder narrative.",
        "# Public Function: Existing outer narrative.",
        "    # Internal Function: Existing nested private narrative.",
    ):
        assert expected in fixed
    assert "TODO" not in "\n".join(fixed)


def test_nested_class_panels_keep_stories_adjacent_and_indentation() -> None:
    """Inserted panels preserve story adjacency for outer and nested classes."""
    lines = [
        "# Outer class story.",
        "class Outer:",
        "    # Inner class story.",
        "    class Inner:",
        "        pass",
    ]

    fixed = code_fixer.fix_class_panels(lines)

    for class_line in ("class Outer:", "    class Inner:"):
        class_idx = fixed.index(class_line)
        panel = [line.strip() for line in fixed[class_idx - 3 : class_idx]]
        assert panel == code_fixer.CLASS_PANEL
    assert fixed[:4] == ["# Outer class story.", *code_fixer.CLASS_PANEL]
    inner_story_idx = fixed.index("    # Inner class story.")
    assert fixed[inner_story_idx + 1 : inner_story_idx + 4] == [
        "    " + line for line in code_fixer.CLASS_PANEL
    ]


def test_class_panel_moves_before_multiline_decorators() -> None:
    """A story and structural panel precede decorators, including misplaced old panels."""
    lines = [
        "# Decorated class story.",
        "@register",
        "@configure(",
        '    option="value",',
        ")",
        "#===== malformed =====#",
        "# Class Definition #",
        "#===== malformed =====#",
        "class Decorated:",
        "    pass",
    ]
    expected = [
        "# Decorated class story.",
        *code_fixer.CLASS_PANEL,
        "@register",
        "@configure(",
        '    option="value",',
        ")",
        "class Decorated:",
        "    pass",
    ]

    fixed = code_fixer.fix_class_panels(lines)

    assert fixed == expected
    assert code_fixer.fix_class_panels(fixed) == expected


def test_keyword_alignment_rewrites_only_simple_separator_whitespace() -> None:
    """Nested calls and complex single-line values survive exact separator edits."""
    lines = [
        "result = configure(",
        '    required=build("x"),',
        '    longer_name  =  {"a": 1},  # Preserve this suffix.',
        "    mid = [1, 2],",
        ")",
    ]

    fixed = code_fixer.fix_keyword_alignment(lines)

    assert fixed == [
        "result = configure(",
        '    required    = build("x"),',
        '    longer_name = {"a": 1},  # Preserve this suffix.',
        "    mid         = [1, 2],",
        ")",
    ]
    _assert_ast_equivalent(lines, fixed)


def test_keyword_alignment_skips_multiline_values_and_nested_ambiguity() -> None:
    """Outer multiline arguments stay verbatim while simple inner groups remain safe."""
    lines = [
        "result = configure(",
        "    required=build(",
        '        "value",',
        "        option=True,",
        "    ),",
        "    other=merge(",
        "        left=1,",
        "        right=2,",
        "    ),",
        "    final=3,",
        ")",
        "same_line = call(first=1, second=2)",
    ]

    fixed = code_fixer.fix_keyword_alignment(lines)

    assert fixed[1] == "    required=build("
    assert fixed[5] == "    other=merge("
    assert fixed[9] == "    final=3,"
    assert fixed[11] == "same_line = call(first=1, second=2)"
    _assert_ast_equivalent(lines, fixed)


def test_dict_alignment_preserves_values_and_skips_multiline_entries() -> None:
    """Dictionary separator edits never synthesize keys or reconstruct values."""
    lines = [
        "payload = {",
        '    "a":build("x"),',
        '    "longer"  :  {"nested": True},',
        "    \"mid\": [1, 2],  # Preserve this suffix.",
        "}",
    ]

    fixed = code_fixer.fix_dict_alignment(lines)

    assert fixed == [
        "payload = {",
        '    "a"      : build("x"),',
        '    "longer" : {"nested": True},',
        "    \"mid\"    : [1, 2],  # Preserve this suffix.",
        "}",
    ]
    _assert_ast_equivalent(lines, fixed)

    multiline_lines = [
        "nested_payload = {",
        '    "short": {',
        '        "nested":1,',
        '        "longer":2,',
        "    },",
        '    "longer":[',
        "        1,",
        "        2,",
        "    ],",
        "}",
    ]
    multiline_fixed = code_fixer.fix_dict_alignment(multiline_lines)
    assert multiline_fixed[1] == '    "short": {'
    assert multiline_fixed[5] == '    "longer":['
    _assert_ast_equivalent(multiline_lines, multiline_fixed)

    same_line = ['payload = {"first":1, "second":2}']
    assert code_fixer.fix_dict_alignment(same_line) == same_line


def test_import_block_removes_blanks_without_reordering_imports() -> None:
    """Even local imports retain their original potentially significant order."""
    lines = [
        "# demo/sample.py",
        "import z",
        "",
        "from demo.z import z",
        "import os",
        "",
        "from demo.a import a",
        "",
        "value = 1",
    ]

    fixed = code_fixer.fix_import_block(lines, "demo")

    assert fixed == [
        "# demo/sample.py",
        "import z",
        "from demo.z import z",
        "import os",
        "from demo.a import a",
        "",
        "value = 1",
    ]


def test_dry_run_prints_unified_diff_without_writing_or_backing_up(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run output is reviewable and leaves every on-disk file untouched."""
    root, path = _make_project(tmp_path, "demo")
    original = path.read_bytes()

    result = code_fixer.main([str(path)])

    output = capsys.readouterr().out
    assert result == 0
    assert "---" in output
    assert "+++" in output
    assert "@@" in output
    assert "-# old/header.py" in output
    assert "+# demo/sample.py" in output
    assert path.read_bytes() == original
    assert not path.with_suffix(".py.bak").exists()
    assert root == tmp_path / "demo"


def test_cli_rejects_removed_chunk_comment_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The deleted generation feature is absent from the public CLI."""
    with pytest.raises(SystemExit) as exc_info:
        code_fixer.main(["--add-chunk-comments", "sample.py"])

    assert exc_info.value.code == 2
    assert "unrecognized arguments: --add-chunk-comments" in capsys.readouterr().err


def test_multiple_inputs_use_independent_project_roots(tmp_path: Path) -> None:
    """Each input derives its own nearest project name and header."""
    _, first = _make_project(tmp_path, "alpha")
    _, second = _make_project(tmp_path, "beta")

    result = code_fixer.main(
        ["--write", "--no-backup", str(first), str(second)]
    )

    assert result == 0
    assert first.read_text().splitlines()[0] == "# alpha/sample.py"
    assert second.read_text().splitlines()[0] == "# beta/sample.py"


def test_fix_file_rejects_string_literal_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The final safety net refuses otherwise valid literal mutations."""
    root, path = _make_project(tmp_path, "demo")
    path.write_text(
        '# demo/sample.py\nMESSAGE = "original"\n', encoding="utf-8"
    )

    def corrupt_literal(lines: list[str]) -> list[str]:
        """Simulate a regression in any textual transformation."""
        return [line.replace("original", "changed") for line in lines]

    monkeypatch.setattr(code_fixer, "collapse_blank_lines", corrupt_literal)
    fixed, summary = code_fixer.fix_file(path, root, "demo")

    assert fixed is None
    assert summary["error"] == "string literal values changed after fixes"
    assert 'MESSAGE = "original"' in path.read_text(encoding="utf-8")
