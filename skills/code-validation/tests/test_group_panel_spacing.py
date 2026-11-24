# graphagents/skills/code-validation/tests/test_group_panel_spacing.py
"""Regression coverage for the required blank line after method group panels."""
import importlib
from pathlib import Path

from test_code_validator import _load_validator, _write_project

PANEL = (
    "#================================================================#\n"
    # Pad the complete panel-middle description the same way the validator does.
    "# Method Group: Fixture operations                               #\n"
    "#================================================================#\n"
)
_LEAD_AND_DEF = (
    "# Public Method: Return a demonstrative placeholder value.\n"
    "def build_demo():\n"
    "    return 1\n"

)


def _write_example(project_root, gap):
    # Parameterize the only structural difference: post-panel spacing.
    body = f"# demo/panelled.py\n{PANEL}{gap}{_LEAD_AND_DEF}"
    (project_root / "panelled.py").write_text(body, encoding = "utf-8")


# Public Function: Reject a method panel whose first definition follows immediately.
def test_method_group_requires_blank_after_panel(tmp_path, capsys):
    # This group has no blank separator and must be reported.
    _write_project(tmp_path)
    _write_example(tmp_path, gap = "")
    validator = _load_validator()
    exit_status = validator.main([str(tmp_path / "panelled.py")])
    assert exit_status == validator.EXIT_VIOLATIONS == 1
    assert "must be followed by one blank line" in capsys.readouterr().out

# Public Function: Accept exactly one blank separator after a method group panel.
def test_method_group_accepts_single_blank_after_panel(tmp_path):
    # The one empty line after the panel is the requested format, not a style bug.
    _write_project(tmp_path)
    _write_example(tmp_path, gap = "\n")
    validator = _load_validator()
    assert validator.main([str(tmp_path / "panelled.py")]) == validator.EXIT_PASS == 0
