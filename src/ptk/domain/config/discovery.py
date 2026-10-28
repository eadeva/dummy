"""Names reserved for generated data and installed dependencies."""

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".repo",
        ".ptk",
        ".venv",
        "venv",
        "node_modules",
        "site-packages",
        "__pycache__",
        "_build",
        "_builds",
        "_bin",
        "_logs",
        "_reports",
        "dist",
    }
)
