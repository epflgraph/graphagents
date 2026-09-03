# graphregistry/.opencode/skills/code-validation/code_validator.py
import argparse, tomllib, rich, io, tokenize, ast
from pathlib import Path

# Set up argument parser to accept a file path as a command-line argument
parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
args = parser.parse_args()

# Read the file and split it into lines
text = args.path.read_text(encoding="utf-8")
text_split = text.splitlines()

# Get project name from pyproject.toml
pyproject_path = next((parent / "pyproject.toml" for parent in args.path.resolve().parents if (parent / "pyproject.toml").exists()), None)
assert pyproject_path is not None, f"pyproject.toml not found in any parent of {args.path}"
with pyproject_path.open("rb") as f:
    pyproject = tomllib.load(f)
project_name = pyproject.get("project", {}).get("name")
assert project_name is not None, "Project name not found in [project] section of pyproject.toml"

# Initialize a list to collect assertion errors
assertion_errors = []

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

# Assert that the first line of the file matches the expected format
if text_split[0] != expected_first_line:
    assertion_errors.append(f"First line should be '{expected_first_line}' but got '{text_split[0]}'")

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
if text_split[last_import_index]=="":
    n_linebreaks -= 1

# Assert that there are no line breaks between import statements
if n_linebreaks != 0:
    assertion_errors.append(f"Expected no line breaks between import statements, but found {n_linebreaks}")

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

    # If we have found a local import, set the flag to True. If we find a
    # non-local import after a local import, raise an AssertionError.
    if is_local_import:
        found_local_import = True
    elif found_local_import:
        assertion_errors.append(
            f"Non-local import found after local imports: '{line}'. "
            f"All imports from '{project_name}' must be at the end of the import section."
        )

#==========================================================================================#
# Rule check: Local module imports must be in alphabetical order within the import section #
#==========================================================================================#

# Get all local import lines from the import section
local_import_lines = [line for line in import_lines if line.startswith(f"import {project_name}") or line.startswith(f"from {project_name}")]

# Check that local imports are in alphabetical order
if local_import_lines != sorted(local_import_lines):
    assertion_errors.append(f"Local imports are not in alphabetical order.")

#===================================#
# Rule check: No double line breaks #
#===================================#

# Check for double line breaks
for i in range(1, len(text_split)):
    if text_split[i] == "" and text_split[i - 1] == "":
        assertion_errors.append(f"Double line break found at line {i + 1}.")

#===============================================================#
# Rule check: Class definition comment panels before each class #
#===============================================================#

# Class pannel template
class_panel_template = [
    "#==================#",
    "# Class Definition #",
    "#==================#"
]

# Locate all class definitions in the file
class_indices = [i for i, line in enumerate(text_split) if line.strip().startswith("class ")]

# Check that each class definition is preceded by the class panel comment
for class_index in class_indices:
    # Check if the class panel is present before the class definition
    if class_index < len(class_panel_template) or text_split[class_index - len(class_panel_template):class_index] != class_panel_template:
        formatted_panel = "  " + "\n  ".join(class_panel_template)
        assertion_errors.append(
            f"Class definition at line {class_index + 1} is not preceded by the required class panel comment:"
            f"[green]\n{formatted_panel}[/green]"
        )

#=====================================================================#
# Rule check: Function/method definition comment before each function #
#=====================================================================#

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

# Locate all function and method definitions in the file
function_indices = [
    i
    for i, line in enumerate(text_split)
    if line.strip().startswith("def ")
]

# Check that each function/method definition is preceded by an allowed descriptive comment
for func_index in function_indices:
    comment_index = func_index - 1

    # Walk backwards over decorators
    while comment_index >= 0 and text_split[comment_index].strip().startswith("@"):
        comment_index -= 1

    # Get the descriptive comment before the function/decorators
    comment = text_split[comment_index].strip() if comment_index >= 0 else ""

    # Check for one of the allowed function/method comment types
    if not comment.startswith(function_comment_prefixes):
        allowed_formats = ", ".join(prefix + "<Description>" for prefix in function_comment_prefixes)
        assertion_errors.append(
            f"Function/method definition at line {func_index + 1} is not preceded "
            f"by an allowed descriptive comment. Expected one of: "
            f"[green]{allowed_formats}[/green]"
        )

#========================================================#
# Rule check: Every code chunk must start with a comment #
#========================================================#

# Find all lines occupied by multiline strings/docstrings
multiline_string_lines = set()

# Use the tokenize module to identify multiline strings/docstrings
tokens = tokenize.generate_tokens(io.StringIO(text).readline)

# Update the set of lines occupied by multiline strings/docstrings
for token in tokens:
    if token.type == tokenize.STRING and token.start[0] != token.end[0]:
        multiline_string_lines.update(
            range(token.start[0] - 1, token.end[0])
        )

# Split the file into chunks separated by blank lines
chunks = []
current_chunk = []

# Iterate through the lines and group them into chunks, ignoring lines that are part of multiline strings/docstrings.
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

# Check that every chunk starts with a comment
for chunk in chunks:
    chunk_start_index, chunk_start_line = chunk[0]

    if not chunk_start_line.strip().startswith("#"):
        assertion_errors.append(
            f"Code chunk starting at line {chunk_start_index + 1} is not preceded "
            f"by an explanatory comment."
        )

#===============================================================#
# Rule check: Comments must not exceed N characters             #
#===============================================================#

# Set the maximum allowed length for comments
max_comment_length = 128

# Check each line to see if it is a comment and exceeds the maximum length
for i, line in enumerate(text_split):
    stripped_line = line.lstrip()

    # Only check comment lines
    if stripped_line.startswith("#"):
        if len(line) > max_comment_length:
            assertion_errors.append(
                f"Comment at line {i + 1} exceeds {max_comment_length} characters "
                f"({len(line)} characters): [green]{line}[/green]"
                f"\n  Use line breaks or rephrase the comment to fit within the limit."
            )

#================================================================#
# Rule check: Function Group panels must have the correct format #
#================================================================#

# Define the expected format for Method Group panels
panel_inner_width = 64
panel_border = f"#{'=' * panel_inner_width}#"
panel_prefix = "# Function Group: "

# Check each line to see if it starts with the Function Group panel comment
for i, line in enumerate(text_split):
    if line.strip().startswith("# Function Group:"):
        indentation = line[:len(line) - len(line.lstrip())]

        # Remove indentation before validating the panel
        panel_line = line[len(indentation):]

        # Check that the description fits within the panel
        description = panel_line.removeprefix(panel_prefix).removesuffix("#").rstrip()
        expected_middle = f"{panel_prefix}{description}".ljust(panel_inner_width + 1) + "#"

        # Build the expected panel
        expected_panel = [
            indentation + panel_border,
            indentation + expected_middle,
            indentation + panel_border,
        ]

        # Get the actual panel
        actual_panel = text_split[i - 1:i + 2]

        if actual_panel != expected_panel:
            formatted_panel = "\n  ".join(expected_panel)

            assertion_errors.append(
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
        indentation = line[:len(line) - len(line.lstrip())]

        # Remove indentation before validating the panel
        panel_line = line[len(indentation):]

        # Extract the description
        description = panel_line.removeprefix(panel_prefix).removesuffix("#").rstrip()

        # Build the expected middle line
        expected_middle = f"{panel_prefix}{description}".ljust(panel_inner_width + 1) + "#"

        # Build the expected panel
        expected_panel = [
            indentation + panel_border,
            indentation + expected_middle,
            indentation + panel_border,
        ]

        # Get the actual panel
        actual_panel = text_split[i - 1:i + 2]

        # Check if the actual panel matches the expected panel
        if actual_panel != expected_panel:
            formatted_panel = "\n  ".join(expected_panel)
            assertion_errors.append(
                f"Method Group panel at line {i + 1} has an invalid format. "
                f"Expected:[green]\n  {formatted_panel}[/green]"
            )

#===================================================================#
# Rule check: Keyword argument "=" signs must be vertically aligned #
#===================================================================#

# Parse the code into an Abstract Syntax Tree (AST) to analyze function calls and their keyword arguments
tree = ast.parse(text)

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

            # Generate the expected lines with vertically aligned "=" signs
            for keyword in group:
                line = text_split[keyword.lineno - 1]
                indentation = line[:len(line) - len(line.lstrip())]

                # Everything after the first "="
                value = line.split("=", 1)[1].lstrip()

                # Append the expected line with the keyword argument name left-justified to the maximum name length and the value after the "=" sign
                expected_lines.append(
                    f"{indentation}{keyword.arg.ljust(max_name_length)} = {value}"
                )

            # Join the expected lines with a newline and two spaces for formatting
            formatted_lines = "\n  ".join(expected_lines)

            # Append an assertion error message indicating that the keyword arguments must have vertically aligned "=" signs, along with the expected format
            assertion_errors.append(
                f"Keyword arguments starting at line {group[0].lineno} "
                f"must have vertically aligned '=' signs. "
                f"Expected:[green]\n  {formatted_lines}[/green]"
            )

#================================================================#
# Rule check: Dict value separators ":" must be vertically aligned
#================================================================#

# Parse the code into an Abstract Syntax Tree (AST) to analyze dictionary definitions and their key-value pairs
tree = ast.parse(text)

# Walk through the AST nodes to find dictionary definitions with key-value pairs
for node in ast.walk(tree):
    if not isinstance(node, ast.Dict) or len(node.keys) < 2:
        continue

    # Only check dictionary entries written on separate lines
    entries = []

    # Iterate through the keys of the dictionary node to find string-literal keys that are written on a single line
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
                "key": key,
                "line": line,
                "colon_column": colon_column,
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

        # Generate the expected lines with vertically aligned ":" separators
        for entry in group:
            key = entry["key"]
            line = entry["line"]

            # Everything before the existing ":"
            indentation = line[:key.col_offset]
            key_text = line[key.col_offset:key.end_col_offset]

            # Everything after the existing ":"
            value_text = line[entry["colon_column"] + 1:].lstrip()

            # Append the expected line with the key left-justified to the maximum key width and the value after the ":" separator
            expected_lines.append(
                f"{indentation}{key_text.ljust(max_key_width)} : {value_text}"
            )

        # Join the expected lines with a newline and two spaces for formatting
        formatted_lines = "\n  ".join(expected_lines)

        # Append an assertion error message indicating that the dictionary entries must have vertically aligned ":" separators, along with the expected format
        assertion_errors.append(
            f"Dictionary entries starting at line {group[0]['key'].lineno} "
            f"must have vertically aligned ':' separators. "
            f"Expected:[green]\n  {formatted_lines}[/green]"
        )

#======================================================================#
# Print the assertion errors if any, otherwise print a success message #
#======================================================================#
if assertion_errors:
    rich.print(f"\n❌ Code validation [red]FAILED[/red] for [cyan]{args.path}[/cyan].")
    rich.print("\n[bold]Reasons:[/bold]")
    for error in assertion_errors:
        rich.print(f"- {error}")
    rich.print('')
else:
    rich.print(f"✅ Code validation [green]PASSED[/green] for [cyan]{args.path}[/cyan].")
