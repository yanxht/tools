"""ocr_vision — Scan (PDF/image) to clean Markdown via macOS Vision MCP.

This package does not perform OCR itself. It captures the prompt and process
for driving the `macos-vision-mcp` tools (`analyze_document`, `ocr_image`) and
turning their output into clean Markdown.

See README.md and WORKFLOW.md for the full recipe.
"""

__all__ = ["main", "print_recipe", "read_prompt", "list_scans"]


def __getattr__(name: str):
    # Lazy re-export so `python -m ocr_vision` does not import __main__ twice.
    if name in __all__:
        from . import __main__ as _main
        return getattr(_main, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
