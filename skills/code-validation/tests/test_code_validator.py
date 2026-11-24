# graphagents/skills/code-validation/tests/test_code_validator.py
import importlib.util
import sys
from pathlib import Path
import rich

# Locate the validator beside this test directory without importing it during collection.
VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "code_validator.py"

# Internal Function: Load a fresh validator module for an isolated regression test.
def _load_validator():
    # Load by path because the skill directory contains a hyphen.
    spec = importlib.util.spec_from_file_location("code_validator_under_test", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Internal Function: Create the minimal project configuration expected by the validator.
def _write_project(project_root, pyproject_text='[project]\nname = "demo"\n'):
    # Keep every test project self-contained under pytest's temporary directory.
    (project_root / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")

# Public Function: Prove module import performs no argument parsing, I/O, printing, or exiting.
def test_import_is_safe_with_pytest_process_arguments(monkeypatch):
    # Simulate the process arguments that previously triggered argparse during import.
    monkeypatch.setattr(sys, "argv", ["pytest", "--unexpected-validator-argument"])

    # Internal Function: Fail immediately if importing the validator attempts external work.
    def _fail(*args, **kwargs):
        # Convert forbidden import-time behavior into a precise test failure.
        raise AssertionError("validator import attempted file I/O or printing")

    # Block file and output operations before executing the imported module.
    monkeypatch.setattr(Path, "is_file", _fail)
    monkeypatch.setattr(Path, "open", _fail)
    monkeypatch.setattr(Path, "read_text", _fail)
    monkeypatch.setattr(rich, "print", _fail)
    module = _load_validator()
    assert callable(module.main)
    assert module.EXIT_PASS == 0
    assert module.EXIT_VIOLATIONS == 1
    assert module.EXIT_CANNOT_VALIDATE == 2

# Public Function: Prove direct main calls accept module and class stories in canonical layouts.
def test_main_passes_canonical_module_story_import_and_class_layout(tmp_path, monkeypatch, capsys):
    # Isolate direct argument handling from unrelated pytest process arguments.
    monkeypatch.setattr(sys, "argv", ["pytest", "--unexpected-validator-argument"])
    _write_project(tmp_path)
    source = tmp_path / "class_story.py"
    source.write_text(
        "# demo/class_story.py\n"
        "# Explain why this module captures the host platform for its story.\n"
        "import os\n"
        "\n"
        "# Capture the host platform name for the narrative example.\n"
        "platform_name = os.name\n"
        "\n"
        "# Introduce the example's role before presenting its class definition.\n"
        "#==================#\n"
        "# Class Definition #\n"
        "#==================#\n"
        "class PlatformStory:\n"
        "    # Public Method: Tell the platform story captured by this module.\n"
        "    def tell(self) -> str:\n"
        "        # Return the host platform as the conclusion of the example's story.\n"
        "        return platform_name\n"
        "\n"
        "    # Public Method: Return the platform asynchronously through a decorated method.\n"
        "    @staticmethod\n"
        "    async def emit() -> str:\n"
        "        # Produce the same host-platform narrative without requiring an instance.\n"
        "        return platform_name\n"
        "\n"
        "    # Store nested configuration alongside its owning platform story.\n"
        "    #==================#\n"
        "    # Class Definition #\n"
        "    #==================#\n"
        "    class Config:\n"
        "        # Public Method: Initialize configuration with the current platform name.\n"
        "        def __init__(self):\n"
        "            # Preserve the selected platform as this configuration's public state.\n"
        "            self.name = platform_name\n",
        encoding="utf-8",
    )
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_PASS
    assert "PASSED" in captured.out
    assert captured.err == ""

# Public Function: Prove panels may immediately precede simple and multiline class decorators.
def test_decorated_and_nested_classes_accept_adjacent_panels(tmp_path, capsys):
    # Cover decorated outer and nested classes without executing their definitions.
    _write_project(tmp_path)
    source = tmp_path / "decorated_classes.py"
    source.write_text(
        "# demo/decorated_classes.py\n"
        "# Explain why these records use immutable dataclass representations.\n"
        "from dataclasses import dataclass\n"
        "\n"
        "# Describe the outer record before its structural panel and decorator.\n"
        "#==================#\n"
        "# Class Definition #\n"
        "#==================#\n"
        "@dataclass\n"
        "class Outer:\n"
        "    # Store the outer record's display name.\n"
        "    name: str\n"
        "    # Describe the nested record before its multiline decorator.\n"
        "    #==================#\n"
        "    # Class Definition #\n"
        "    #==================#\n"
        "    @dataclass(\n"
        "        frozen=True,\n"
        "    )\n"
        "    class Nested:\n"
        "        # Store the nested record's immutable numeric value.\n"
        "        value: int\n",
        encoding="utf-8",
    )
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_PASS
    assert "PASSED" in captured.out
    assert "Class definition at line" not in captured.out

# Public Function: Prove a decorated class still requires its class panel.
def test_decorated_class_without_panel_is_rejected(tmp_path, capsys):
    # Keep every unrelated convention valid so the missing panel is isolated.
    _write_project(tmp_path)
    source = tmp_path / "missing_class_panel.py"
    source.write_text(
        "# demo/missing_class_panel.py\n"
        "# Explain why this record needs a visible class-story boundary.\n"
        "from dataclasses import dataclass\n"
        "\n"
        "# Describe the record without supplying its required structural panel.\n"
        "@dataclass\n"
        "class MissingPanel:\n"
        "    # Store the record's display name.\n"
        "    name: str\n",
        encoding="utf-8",
    )
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_VIOLATIONS == 1
    assert "Class definition at line 7 is not preceded by the required class panel" in captured.out

# Public Function: Prove a blank line cannot separate a panel from the first decorator.
def test_panel_separated_from_class_decorator_is_rejected(tmp_path, capsys):
    # Leave an otherwise well-formed panel one blank line away from its decorator.
    _write_project(tmp_path)
    source = tmp_path / "misplaced_class_panel.py"
    source.write_text(
        "# demo/misplaced_class_panel.py\n"
        "# Explain why the class panel must remain adjacent to its decorator.\n"
        "from dataclasses import dataclass\n"
        "\n"
        "# Describe the record before its non-adjacent structural panel.\n"
        "#==================#\n"
        "# Class Definition #\n"
        "#==================#\n"
        "\n"
        "@dataclass\n"
        "class MisplacedPanel:\n"
        "    # Store the record's display name.\n"
        "    name: str\n",
        encoding="utf-8",
    )
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_VIOLATIONS == 1
    assert "Class definition at line 11 is not preceded by the required class panel" in captured.out

# Public Function: Prove a module story cannot hide unsorted local imports.
def test_module_story_does_not_bypass_alphabetical_local_import_check(tmp_path, capsys):
    # Place two unsorted project imports directly after a valid module story.
    _write_project(tmp_path)
    source = tmp_path / "unsorted_imports.py"
    source.write_text(
        "# demo/unsorted_imports.py\n"
        "# Explain why this story depends on its local components.\n"
        "from demo.zeta import Zeta\n"
        "from demo.alpha import Alpha\n",
        encoding="utf-8",
    )
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_VIOLATIONS == 1
    assert "Local imports are not in alphabetical order" in captured.out

# Public Function: Prove a module story cannot hide a non-local import after local imports.
def test_module_story_does_not_bypass_local_import_last_check(tmp_path, capsys):
    # Place a standard-library import after a project import in the initial block.
    _write_project(tmp_path)
    source = tmp_path / "misplaced_import.py"
    source.write_text(
        "# demo/misplaced_import.py\n"
        "# Explain why this story depends on its local helpers.\n"
        "from demo.tools import helpers\n"
        "import os\n",
        encoding="utf-8",
    )
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_VIOLATIONS == 1
    assert "Non-local import found after local imports: 'import os'" in captured.out

# Public Function: Prove simple single-line keyword and dictionary entries remain aligned.
def test_simple_keyword_and_dict_misalignment_is_still_reported(tmp_path, capsys):
    # Supply reliable AST-delimited entries that genuinely violate both alignment rules.
    _write_project(tmp_path)
    source = tmp_path / "simple_alignment.py"
    source.write_text(
        "# demo/simple_alignment.py\n"
        "# Explain why these unambiguous arguments demonstrate alignment checks.\n"
        "build(\n"
        "    short=1,\n"
        "    longer_name = 2,\n"
        ")\n"
        "\n"
        "# Provide correspondingly simple dictionary entries for the shared rule.\n"
        "payload = {\n"
        "    \"a\": 1,\n"
        "    \"longer\" : 2,\n"
        "}\n",
        encoding="utf-8",
    )
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_VIOLATIONS == 1
    assert "Keyword arguments starting at line 4" in captured.out
    assert "Dictionary entries starting at line 10" in captured.out

# Public Function: Prove ambiguous and multiline entries never receive rewrite suggestions.
def test_ambiguous_and_multiline_entries_do_not_get_alignment_suggestions(tmp_path, capsys):
    # Combine shared-line entries and multiline values that a safe fixer must leave alone.
    _write_project(tmp_path)
    source = tmp_path / "ambiguous_alignment.py"
    source.write_text(
        "# demo/ambiguous_alignment.py\n"
        "# Explain why overlapping keyword arguments are intentionally left unchanged.\n"
        "build(\n"
        "    first=1, second=2,\n"
        "    third = 3,\n"
        ")\n"
        "\n"
        "# Preserve dictionary entries that would overlap a line-based replacement.\n"
        "payload = {\n"
        "    \"first\": 1, \"second\": 2,\n"
        "    \"third\" : 3,\n"
        "}\n"
        "\n"
        "# Leave multiline keyword values outside the conservative alignment analysis.\n"
        "configure(\n"
        "    first = (\n"
        "        1\n"
        "    ),\n"
        "    second= (\n"
        "        2\n"
        "    ),\n"
        ")\n",
        encoding="utf-8",
    )
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_PASS
    assert "Keyword arguments starting at line" not in captured.out
    assert "Dictionary entries starting at line" not in captured.out

# Public Function: Prove an empty readable source reports a normal header violation.
def test_empty_file_reports_missing_header_without_traceback(tmp_path, capsys):
    # Supply a valid project so only the empty source header is under test.
    _write_project(tmp_path)
    source = tmp_path / "empty.py"
    source.write_text("", encoding="utf-8")
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_VIOLATIONS == 1
    assert "First line should be '# demo/empty.py'" in captured.out
    assert "FAILED" in captured.out
    assert "Traceback" not in captured.out + captured.err

# Public Function: Prove malformed project TOML returns a clean cannot-validate status.
def test_malformed_pyproject_fails_cleanly(tmp_path, capsys):
    # Reach project parsing with a readable source and deliberately malformed TOML.
    _write_project(tmp_path, '[project\nname = "demo"\n')
    source = tmp_path / "broken_config.py"
    source.write_text("# demo/broken_config.py\n", encoding="utf-8")
    module = _load_validator()
    exit_status = module.main([str(source)])
    captured = capsys.readouterr()
    assert exit_status == module.EXIT_CANNOT_VALIDATE == 2
    assert "Cannot read project configuration" in captured.out
    assert "Traceback" not in captured.out + captured.err
