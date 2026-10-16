import ast
import json
from datetime import datetime
from pathlib import Path


# ============================================================
# AI AGENT SOURCE CODE INDEXER
# ============================================================
#
# Reads the actual project source code using Python's AST.
#
# It DOES NOT execute project modules.
#
# Purpose:
#
# Actual source code
#       ↓
# AST inspection
#       ↓
# Exact modules / functions / signatures / classes / imports
#       ↓
# Machine-readable source index
#
# This index is DERIVED knowledge.
# The actual source code remains authoritative.
# ============================================================


PROJECT_ROOT = Path(__file__).resolve().parent.parent

KNOWLEDGE_STORE = (
    PROJECT_ROOT
    / "knowledge"
    / "store"
)

SOURCE_INDEX_PATH = (
    KNOWLEDGE_STORE
    / "source_index.json"
)


# Directories that should never be indexed as project source.

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".kilo",
    ".codex",
    ".claude",
    ".cursor",
    ".opencode",
    "runtime",
}


# ============================================================
# PATH HELPERS
# ============================================================

def relative_path(path):
    """
    Convert an absolute project path into a stable
    project-relative path.
    """

    return str(
        path.relative_to(PROJECT_ROOT)
    ).replace("\\", "/")


def should_ignore(path):
    """
    Return True when a path belongs to an ignored directory.
    """

    try:
        parts = path.relative_to(
            PROJECT_ROOT
        ).parts

    except ValueError:
        return True

    return any(
        part in IGNORED_DIRECTORIES
        for part in parts
    )


# ============================================================
# FUNCTION SIGNATURE EXTRACTION
# ============================================================

def format_default_value(node):
    """
    Convert an AST default-value node into readable source.

    No code is executed.
    """

    try:
        return ast.unparse(node)

    except Exception:
        return "<unavailable>"


def extract_arguments(arguments):
    """
    Convert ast.arguments into structured signature data.
    """

    positional = (
        list(arguments.posonlyargs)
        + list(arguments.args)
    )

    defaults = list(
        arguments.defaults
    )

    default_offset = (
        len(positional)
        - len(defaults)
    )

    parameters = []

    for index, argument in enumerate(
        positional
    ):

        parameter = {
            "name": argument.arg,
            "kind": (
                "positional_only"
                if index
                < len(arguments.posonlyargs)
                else "positional_or_keyword"
            ),
            "default": None,
        }

        if index >= default_offset:

            default_node = defaults[
                index - default_offset
            ]

            parameter["default"] = (
                format_default_value(
                    default_node
                )
            )

        parameters.append(
            parameter
        )

    if arguments.vararg is not None:

        parameters.append(
            {
                "name":
                    arguments.vararg.arg,
                "kind":
                    "var_positional",
                "default":
                    None,
            }
        )

    for argument, default in zip(
        arguments.kwonlyargs,
        arguments.kw_defaults,
    ):

        parameters.append(
            {
                "name":
                    argument.arg,
                "kind":
                    "keyword_only",
                "default": (
                    None
                    if default is None
                    else format_default_value(
                        default
                    )
                ),
            }
        )

    if arguments.kwarg is not None:

        parameters.append(
            {
                "name":
                    arguments.kwarg.arg,
                "kind":
                    "var_keyword",
                "default":
                    None,
            }
        )

    return parameters


def build_signature(
    function_node,
):
    """
    Produce a readable signature using the actual AST.
    """

    parameters = extract_arguments(
        function_node.args
    )

    pieces = []

    for parameter in parameters:

        kind = parameter["kind"]
        name = parameter["name"]
        default = parameter["default"]

        if kind == "var_positional":

            piece = f"*{name}"

        elif kind == "var_keyword":

            piece = f"**{name}"

        else:

            piece = name

            if default is not None:

                piece += (
                    f"={default}"
                )

        pieces.append(piece)

    return (
        function_node.name
        + "("
        + ", ".join(pieces)
        + ")"
    )


# ============================================================
# IMPORT EXTRACTION
# ============================================================

def extract_imports(tree):
    """
    Extract imports from a parsed Python module.
    """

    imports = []

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                imports.append(
                    {
                        "type": "import",
                        "module": alias.name,
                        "name": None,
                        "alias": alias.asname,
                    }
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            module = (
                node.module
                if node.module
                else ""
            )

            for alias in node.names:

                imports.append(
                    {
                        "type": "from",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                    }
                )

    return imports


# ============================================================
# MODULE INSPECTION
# ============================================================

def inspect_python_file(path):
    """
    Inspect one Python file without importing or executing it.
    """

    record = {
        "path": relative_path(path),
        "parse_success": False,
        "error": None,
        "functions": [],
        "classes": [],
        "imports": [],
    }

    try:

        source = path.read_text(
            encoding="utf-8"
        )

    except Exception as error:

        record["error"] = (
            f"Read failed: {error}"
        )

        return record

    try:

        tree = ast.parse(
            source,
            filename=str(path),
        )

    except SyntaxError as error:

        record["error"] = (
            f"Syntax error: {error}"
        )

        return record

    record["parse_success"] = True

    record["imports"] = (
        extract_imports(tree)
    )

    # Only top-level definitions are indexed here.
    # Methods are stored inside their owning class.

    for node in tree.body:

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):

            record["functions"].append(
                {
                    "name":
                        node.name,

                    "signature":
                        build_signature(
                            node
                        ),

                    "async":
                        isinstance(
                            node,
                            ast.AsyncFunctionDef,
                        ),

                    "line":
                        node.lineno,
                }
            )

        elif isinstance(
            node,
            ast.ClassDef,
        ):

            class_record = {
                "name": node.name,
                "line": node.lineno,
                "methods": [],
            }

            for class_node in node.body:

                if isinstance(
                    class_node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ):

                    class_record[
                        "methods"
                    ].append(
                        {
                            "name":
                                class_node.name,

                            "signature":
                                build_signature(
                                    class_node
                                ),

                            "async":
                                isinstance(
                                    class_node,
                                    ast.AsyncFunctionDef,
                                ),

                            "line":
                                class_node.lineno,
                        }
                    )

            record["classes"].append(
                class_record
            )

    return record


# ============================================================
# PROJECT DISCOVERY
# ============================================================

def discover_python_files():
    """
    Discover project Python files while excluding environments
    and generated dependency directories.
    """

    files = []

    for path in PROJECT_ROOT.rglob(
        "*.py"
    ):

        if should_ignore(path):
            continue

        files.append(path)

    return sorted(
        files,
        key=lambda item:
            relative_path(item).lower(),
    )


# ============================================================
# BUILD INDEX
# ============================================================

def build_source_index():
    """
    Build an in-memory source-code index.
    """

    python_files = (
        discover_python_files()
    )

    modules = []

    parse_failures = 0
    function_count = 0
    class_count = 0

    for path in python_files:

        module = (
            inspect_python_file(
                path
            )
        )

        modules.append(module)

        if not module[
            "parse_success"
        ]:

            parse_failures += 1

        function_count += len(
            module["functions"]
        )

        class_count += len(
            module["classes"]
        )

    return {
        "schema_version": "1.0",

        "generated_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "project_root": (
            str(PROJECT_ROOT)
        ),

        "statistics": {
            "python_files":
                len(python_files),

            "top_level_functions":
                function_count,

            "classes":
                class_count,

            "parse_failures":
                parse_failures,
        },

        "modules": modules,
    }


# ============================================================
# SAVE INDEX
# ============================================================

def save_source_index():
    """
    Generate and save source_index.json.
    """

    KNOWLEDGE_STORE.mkdir(
        parents=True,
        exist_ok=True,
    )

    index = build_source_index()

    SOURCE_INDEX_PATH.write_text(
        json.dumps(
            index,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return index


# ============================================================
# LOOKUP
# ============================================================

def find_function(
    function_name,
    index=None,
):
    """
    Find exact top-level function definitions by name.
    """

    if index is None:

        index = build_source_index()

    matches = []

    for module in index[
        "modules"
    ]:

        for function in module[
            "functions"
        ]:

            if (
                function["name"]
                == function_name
            ):

                matches.append(
                    {
                        "path":
                            module["path"],

                        **function,
                    }
                )

    return matches


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("SOURCE CODE INDEXER")
    print("==============================")

    index = save_source_index()

    statistics = index[
        "statistics"
    ]

    print()
    print(
        "Python files:",
        statistics[
            "python_files"
        ],
    )

    print(
        "Top-level functions:",
        statistics[
            "top_level_functions"
        ],
    )

    print(
        "Classes:",
        statistics[
            "classes"
        ],
    )

    print(
        "Parse failures:",
        statistics[
            "parse_failures"
        ],
    )

    print()
    print("record_event SIGNATURE")

    matches = find_function(
        "record_event",
        index,
    )

    for match in matches:

        print(
            match["path"],
            "->",
            match["signature"],
        )

    print()
    print(
        "Index saved to:",
        SOURCE_INDEX_PATH,
    )