# ~/.config/opencode/skills/code-validation/code_validator.py
import argparse, ast, io, sys, tokenize, tomllib
import rich
from pathlib import Path

# Exit codes used by this script so that CI, pre-commit hooks, and shell chains can
# gate on the result: 0 = validation passed, 1 = style violations found,
# 2 = the file could not be validated at all (missing project, unreadable, syntax error).
EXIT_PASS            = 0
EXIT_VIOLATIONS      = 1
EXIT_CANNOT_VALIDATE = 2

# Maximum allowed length of a comment line, in columns.
# NOTE: code_fixer.py currently wraps comments at 112 columns and SKILL.md mentions
# both 92 and 128 in different sections. These values must be unified in a follow-up
# pass; 128 is kept here so that fixer output always passes this check.
MAX_COMMENT_LENGTH = 128

# Set up argument parser to accept a file path as a command-line argument
parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
args = parser.parse_args()

#--------------------------------------------------------------------------------------------#
# Preliminary checks: the file must be readable and belong to a project with a pyproject.toml #
#--------------------------------------------------------------------------------------------#

# Reject paths that do not point at a regular file, with a clean message instead of a traceback
if not args.path.is_file():
    rich.print(f"❌ Cannot validate [cyan]{args.path}[/cyan]: not a file.")
    sys.exit(EXIT_CANNOT_VALIDATE)

# Read the target file; decoding or I/O problems are validation blockers, not violations
try:
    text = args.path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError) as read_error:
    rich.print(f"❌ Cannot validate [cyan]{args.path}[/cyan]: {read_error}")
    sys.exit(EXIT_CANNOT_VALIDATE)

# Read the file and split it into lines
text_split = text.splitlines()

# Get project name from pyproject.toml
pyproject_path = next((parent / "pyproject.toml" for parent in args.path.resolve().parents if (parent / "pyproject.toml").exists()), None)
if pyproject_path is None:
    rich.print(f"❌ Cannot validate [cyan]{args.path}[/cyan]: no pyproject.toml found in any parent directory.")
    sys.exit(EXIT_CANNOT_VALIDATE)

with pyproject_path.open("rb") as f:
    pyproject = tomllib.load(f)
project_name = pyproject.get("project", {}).get("name")
if project_name is None:
    rich.print(f"❌ Project name not found in [project] section of {pyproject_path}")
    sys.exit(EXIT_CANNOT_VALIDATE)

# Parse the file once. The AST is reused by the alignment rules and doubles as the
# syntax gate, so broken files fail with a clean message instead of a mid-check crash.
try:
    tree = ast.parse(text)
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
except (SyntaxError, tokenize.TokenError, ValueError) as parse_error:
    lineno  = getattr(parse_error, "lineno", None)
    message = getattr(parse_error, "msg", None) or str(parse_error)
    location = f" at line {lineno}" if lineno is not None else ""
    rich.print(f"❌ Cannot validate [cyan]{args.path}[/cyan]: syntax error{location}: {message}")
    sys.exit(EXIT_CANNOT_VALIDATE)

# Initialize a list to collect validation errors
validation_errors = []

#========================================================================================#
# Rule check: First line must be the file path as a comment (starting with project name) #
#========================================================================================#

# Get the relative path of the file to the project root and ensure it starts with the project name
local_path = args.path.resolve().relative_to(pyproject_path.parent)

# Ensure the local path starts with the project name
if local_path.parts[0] != project_name:
    local_path = Path(project_name) / local_path

# Check that the first line of the file matches the expected format
expected_first_line = f"# {local_path.as_posix()}"

# Report a violation when the first line does not match the expected header format
if text_split[0] != expected_first_line:
    validation_errors.append(f"First line should be '{expected_first_line}' but got '{text_split[0]}'")

#=================================================================================#
# Shared input: lines occupied by multiline strings, used by several rules below #
#=================================================================================#

# Find all lines occupied by multiline strings/docstrings so that the line-based rules
# (class/def detection, chunk splitting, comment length) never match against string
# content. Single-line strings are irrelevant because they cannot span a chunk boundary.
multiline_string_lines = set()
for token in tokens:
    if token.type == tokenize.STRING and token.start[0] != token.end[0]:
        multiline_string_lines.update(
            range(token.start[0] - 1, token.end[0])
        )

#====================================================================#
# Rule check: There must be no line breaks between import statements #
#====================================================================#

# Search for the last import statement at the beginning of the file
# and count the number of line breaks between import statements
last_import_index = 1
n_linebreaks = 0
for i, line in enumerate(text_split[1:], start=1):
    if line.startswith("import") or line.startswith("from") or line.strip() == "":
        last_import_index = i
        if line.strip() == "":
            n_linebreaks += 1
    else:
        break

# Guard against very small files where the import section is empty, then drop the
# trailing blank line that simply separates the import section from the first chunk
if last_import_index < len(text_split) and text_split[last_import_index] == "":
    n_linebreaks -= 1

# Report a violation when blank lines interrupt the import section
if n_linebreaks != 0:
    validation_errors.append(f"Expected no line breaks between import statements, but found {n_linebreaks}")

#===========================================================================#
# Rule check: Local module imports must be at the end of the import section #
#===========================================================================#

# Get all import lines from the import section
import_lines = [line for line in text_split[1:last_import_index + 1] if line.startswith("import ") or line.startswith("from ")]

# Track whether we have reached the local-import section
found_local_import = False

# Check that all local imports (from the project) are at the end of the import section
for line in import_lines:

    # Determine if the current line is a local import (from the project)
    is_local_import = (line.startswith(f"import {project_name}") or line.startswith(f"from {project_name}"))

    # Once the local-import section has started, no non-local import may follow it
    if is_local_import:
        found_local_import = True
    elif found_local_import:
        validation_errors.append(
            f"Non-local import found after local imports: '{line}'. "
            f"All imports from '{project_name}' must be at the end of the import section."
        )

#==========================================================================================#
# Rule check: Local module imports must be in alphabetical order within the import section #
#==========================================================================================#

# Get all local import lines from the import section
local_import_lines = [line for line in import_lines if line.startswith(f"import {project_name}") or line.startswith(f"from {project_name}")]

# Report a violation when local imports are not sorted alphabetically
if local_import_lines != sorted(local_import_lines):
    validation_errors.append(f"Local imports are not in alphabetical order.")

#===================================#
# Rule check: No double line breaks #
#===================================#

# Report every occurrence of two consecutive blank lines
for i in range(1, len(text_split)):
    if text_split[i] == "" and text_split[i - 1] == "":
        validation_errors.append(f"Double line break found at line {i + 1}.")

#===============================================================#
# Rule check: Class definition comment panels before each class #
#===============================================================#

# Class panel template
class_panel_template = [
    "#==================#",
    "# Class Definition #",
    "#==================#"
]

# Locate all class definitions in the file, ignoring lines inside multiline strings
class_indices = [
    i
    for i, line in enumerate(text_split)
    if i not in multiline_string_lines and line.strip().startswith("class ")
]

# Check that each class definition is preceded by the class panel comment. The panel
# may carry the same indentation as its class so that nested classes can comply, so
# indentation is stripped before comparing against the template.
for class_index in class_indices:

    # A class near the top of the file cannot carry a three-line panel above it
    if class_index < len(class_panel_template):
        panel_is_valid = False
    else:
        preceding_lines = text_split[class_index - len(class_panel_template):class_index]
        panel_is_valid = [line.strip() for line in preceding_lines] == class_panel_template

    # Report a violation when the panel is missing or malformed
    if not panel_is_valid:
        formatted_panel = "  " + "\n  ".join(class_panel_template)
        validation_errors.append(
            f"Class definition at line {class_index + 1} is not preceded by the required class panel comment:"
            f"[green]\n{formatted_panel}[/green]"
        )

#=====================================================================================#
# Rule check: Function/method definitions must be introduced by a tagged lead comment #
#=====================================================================================#

# Define the allowed function/method comment prefixes
function_comment_prefixes = (
    "# Function: ",
    "# Method: ",
    "# Helper Function: ",
    "# Helper Method: ",
    "# Internal Function: ",
    "# Internal Method: ",
    "# Public Function: ",
    "# Public Method: ",
)

# Locate all function and method definitions, including 'async def', ignoring lines
# inside multiline strings
function_indices = [
    i
    for i, line in enumerate(text_split)
    if i not in multiline_string_lines
    and (line.strip().startswith("def ") or line.strip().startswith("async def "))
]

# Check that each definition is introduced by a contiguous comment block containing at
# least one line with an allowed type tag. The block must sit directly above the
# definition or its decorators, with no blank line in between.
for func_index in function_indices:
    cursor = func_index - 1

    # Walk backwards over decorators so the lead comment is found above them
    while cursor >= 0 and text_split[cursor].strip().startswith("@"):
        cursor -= 1

    # Walk backwards over the contiguous comment block that introduces the definition
    block_end = cursor
    while block_end >= 0 and text_split[block_end].strip().startswith("#"):
        block_end -= 1
    comment_block = text_split[block_end + 1:cursor + 1]

    # The block passes when any of its lines opens with an allowed type tag; this
    # accepts multi-line descriptions that continue below the tagged first line
    block_is_tagged = any(
        comment_line.strip().startswith(function_comment_prefixes)
        for comment_line in comment_block
    )

    # Report a violation when there is no adjacent comment block or no tagged line
    if not comment_block or not block_is_tagged:
        allowed_formats = ", ".join(prefix + "<Description>" for prefix in function_comment_prefixes)
        validation_errors.append(
            f"Function/method definition at line {func_index + 1} is not introduced "
            f"by an allowed descriptive comment. Expected one of: "
            f"[green]{allowed_formats}[/green] "
            f"The comment block must sit directly above the definition or its "
            f"decorators, with no blank line in between."
        )

#========================================================#
# Rule check: Every code chunk must start with a comment #
#========================================================#

# Split the file into chunks separated by blank lines, ignoring lines that belong to
# multiline strings/docstrings
chunks = []
current_chunk = []

# Iterate through the lines and group them into chunks
for i, line in enumerate(text_split):

    # Ignore lines belonging to multiline strings/docstrings
    if i in multiline_string_lines:
        continue

    # If the line is blank, finalize the current chunk and start a new one
    if line.strip() == "":
        if current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
    else:
        current_chunk.append((i, line))

# Add the final chunk
if current_chunk:
    chunks.append(current_chunk)

# Check that every chunk starts with a comment line
for chunk in chunks:
    chunk_start_index, chunk_start_line = chunk[0]

    if not chunk_start_line.strip().startswith("#"):
        validation_errors.append(
            f"Code chunk starting at line {chunk_start_index + 1} does not start with "
            f"an explanatory comment. Place the comment directly above the chunk, with "
            f"no blank line between the comment and the code."
        )

#================================================================#
# Rule check: Comments must not exceed the maximum column width #
#================================================================#

# Check each comment line against the shared maximum length, ignoring lines inside
# multiline strings because they are string content rather than comments
for i, line in enumerate(text_split):
    stripped_line = line.lstrip()

    # Only check real comment lines
    if stripped_line.startswith("#") and i not in multiline_string_lines:
        if len(line) > MAX_COMMENT_LENGTH:
            validation_errors.append(
                f"Comment at line {i + 1} exceeds {MAX_COMMENT_LENGTH} characters "
                f"({len(line)} characters): [green]{line}[/green]"
                f"\n  Use line breaks or rephrase the comment to fit within the limit."
            )

#================================================================#
# Rule check: Function Group panels must have the correct format #
#================================================================#

# Define the expected format for Function Group panels
panel_inner_width = 64
panel_border = f"#{'=' * panel_inner_width}#"
panel_prefix = "# Function Group: "

# Check each line to see if it starts with the Function Group panel comment
for i, line in enumerate(text_split):
    if line.strip().startswith("# Function Group:"):

        # Extract the indentation so the panel can be validated without it
        indentation = line[:len(line) - len(line.lstrip())]
        panel_line = line[len(indentation):]

        # Extract the description from the panel line
        description = panel_line.removeprefix(panel_prefix).removesuffix("#").rstrip()

        # Build the expected middle line, padded to the panel width
        expected_middle = f"{panel_prefix}{description}".ljust(panel_inner_width + 1) + "#"

        # Build the full expected panel
        expected_panel = [
            indentation + panel_border,
            indentation + expected_middle,
            indentation + panel_border,
        ]

        # Compare against the actual panel surrounding the current line
        actual_panel = text_split[i - 1:i + 2]

        if actual_panel != expected_panel:
            formatted_panel = "\n  ".join(expected_panel)
            validation_errors.append(
                f"Function Group panel at line {i + 1} has an invalid format. "
                f"Expected:[green]\n  {formatted_panel}[/green]"
            )

#================================================================#
# Rule check: Method Group panels must have the correct format   #
#================================================================#

# Define the expected format for Method Group panels
panel_inner_width = 64
panel_border = f"#{'=' * panel_inner_width}#"
panel_prefix = "# Method Group: "

# Check each line to see if it starts with the Method Group panel comment
for i, line in enumerate(text_split):
    if line.strip().startswith("# Method Group:"):

        # Extract the indentation so the panel can be validated without it
        indentation = line[:len(line) - len(line.lstrip())]
        panel_line = line[len(indentation):]

        # Extract the description from the panel line
        description = panel_line.removeprefix(panel_prefix).removesuffix("#").rstrip()

        # Build the expected middle line, padded to the panel width
        expected_middle = f"{panel_prefix}{description}".ljust(panel_inner_width + 1) + "#"

        # Build the full expected panel
        expected_panel = [
            indentation + panel_border,
            indentation + expected_middle,
            indentation + panel_border,
        ]

        # Compare against the actual panel surrounding the current line
        actual_panel = text_split[i - 1:i + 2]

        if actual_panel != expected_panel:
            formatted_panel = "\n  ".join(expected_panel)
            validation_errors.append(
                f"Method Group panel at line {i + 1} has an invalid format. "
                f"Expected:[green]\n  {formatted_panel}[/green]"
            )

#===================================================================#
# Rule check: Keyword argument "=" signs must be vertically aligned #
#===================================================================#

# Walk through the AST nodes to find function calls with keyword arguments
for node in ast.walk(tree):
    if not isinstance(node, ast.Call) or len(node.keywords) < 2:
        continue

    # Only check keyword arguments written on separate lines
    keywords = [
        keyword
        for keyword in node.keywords
        if keyword.arg is not None
        and hasattr(keyword, "lineno")
    ]

    # Skip if there are fewer than 2 keyword arguments on separate lines
    if len(keywords) < 2:
        continue

    # Group consecutive keyword arguments by line
    groups = []
    current_group = []

    # Group consecutive keyword arguments that appear on consecutive lines
    for keyword in keywords:
        if (
            current_group
            and keyword.lineno != current_group[-1].lineno + 1
        ):
            if len(current_group) >= 2:
                groups.append(current_group)
            current_group = []

        # Add the current keyword to the current group
        current_group.append(keyword)

    # Add the last group if it has 2 or more keyword arguments
    if len(current_group) >= 2:
        groups.append(current_group)

    # Check alignment within each group
    for group in groups:
        lines = [
            text_split[keyword.lineno - 1]
            for keyword in group
        ]

        # Find the column index of the "=" sign for each line in the group
        equal_columns = [line.index("=") for line in lines]

        # If the "=" signs are not vertically aligned, generate an error message with the expected alignment
        if len(set(equal_columns)) != 1:
            max_name_length = max(len(keyword.arg) for keyword in group)

            # Generate the expected lines with vertically aligned "=" signs
            expected_lines = []

            for keyword in group:
                line = text_split[keyword.lineno - 1]
                indentation = line[:len(line) - len(line.lstrip())]

                # Everything after the first "="
                value = line.split("=", 1)[1].lstrip()

                # Append the expected line with the keyword argument name left-justified to the maximum name length
                expected_lines.append(
                    f"{indentation}{keyword.arg.ljust(max_name_length)} = {value}"
                )

            # Join the expected lines with a newline and two spaces for formatting
            formatted_lines = "\n  ".join(expected_lines)

            # Report the misaligned keyword arguments along with the expected format
            validation_errors.append(
                f"Keyword arguments starting at line {group[0].lineno} "
                f"must have vertically aligned '=' signs. "
                f"Expected:[green]\n  {formatted_lines}[/green]"
            )

#================================================================#
# Rule check: Dict value separators ":" must be vertically aligned
#================================================================#

# Walk through the AST nodes to find dictionary definitions with key-value pairs
for node in ast.walk(tree):
    if not isinstance(node, ast.Dict) or len(node.keys) < 2:
        continue

    # Only check dictionary entries written on separate lines
    entries = []

    # Iterate through the keys of the dictionary node to find string-literal keys written on a single line
    for key in node.keys:
        # Ignore **mapping entries
        if key is None:
            continue

        # Only enforce alignment for string-literal keys
        if not (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
        ):
            continue

        # Only handle keys written on a single line
        if key.lineno != key.end_lineno:
            continue

        # Get the line of code corresponding to the key's line number
        line = text_split[key.lineno - 1]

        # Find the ":" after the key
        key_end_column = key.end_col_offset
        colon_column = line.find(":", key_end_column)

        # If no ":" is found, skip this key
        if colon_column == -1:
            continue

        # Append the key, line, and colon column to the entries list for further processing
        entries.append(
            {
                "key"          : key,
                "line"         : line,
                "colon_column" : colon_column,
            }
        )

    # Skip if there are fewer than 2 entries to check for alignment
    if len(entries) < 2:
        continue

    # Group entries that appear on consecutive lines
    groups = []
    current_group = []

    # Group consecutive dictionary entries that appear on consecutive lines
    for entry in entries:
        if (
            current_group
            and entry["key"].lineno != current_group[-1]["key"].lineno + 1
        ):
            if len(current_group) >= 2:
                groups.append(current_group)

            # Start a new group for the current entry
            current_group = []

        # Add the current entry to the current group
        current_group.append(entry)

    # Add the last group if it has 2 or more entries
    if len(current_group) >= 2:
        groups.append(current_group)

    # Check alignment within each group
    for group in groups:
        colon_columns = [entry["colon_column"] for entry in group]

        # If the ":" separators are already vertically aligned, skip this group
        if len(set(colon_columns)) == 1:
            continue

        # Find the maximum key width in the group to determine the alignment
        max_key_width = max(
            entry["key"].end_col_offset - entry["key"].col_offset
            for entry in group
        )

        # Generate the expected lines with vertically aligned ":" separators
        expected_lines = []

        for entry in group:
            key = entry["key"]
            line = entry["line"]

            # Everything before the existing ":"
            indentation = line[:key.col_offset]
            key_text = line[key.col_offset:key.end_col_offset]

            # Everything after the existing ":"
            value_text = line[entry["colon_column"] + 1:].lstrip()

            # Append the expected line with the key left-justified to the maximum key width
            expected_lines.append(
                f"{indentation}{key_text.ljust(max_key_width)} : {value_text}"
            )

        # Join the expected lines with a newline and two spaces for formatting
        formatted_lines = "\n  ".join(expected_lines)

        # Report the misaligned dictionary entries along with the expected format
        validation_errors.append(
            f"Dictionary entries starting at line {group[0]['key'].lineno} "
            f"must have vertically aligned ':' separators. "
            f"Expected:[green]\n  {formatted_lines}[/green]"
        )

#=======================================================================#
# Print the validation errors if any, otherwise print a success message #
#=======================================================================#
if validation_errors:
    rich.print(f"\n❌ Code validation [red]FAILED[/red] for [cyan]{args.path}[/cyan].")
    rich.print("\n[bold]Reasons:[/bold]")
    for error in validation_errors:
        rich.print(f"- {error}")
    rich.print('')

    # Non-zero exit code so CI, pre-commit hooks, and shell chains can gate on the result
    sys.exit(EXIT_VIOLATIONS)

rich.print(f"✅ Code validation [green]PASSED[/green] for [cyan]{args.path}[/cyan].")
sys.exit(EXIT_PASS)
