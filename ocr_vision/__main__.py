"""ocr_vision — Scan (PDF/image) to clean Markdown via macOS Vision MCP.

The OCR itself is performed by the `macos-vision-mcp` server (Apple Vision,
local/offline). This helper does two things:

  1. Prints the exact agent recipe for the scan -> Markdown workflow.
  2. Lists candidate scans in a directory so you can pick one.

Usage:
    python -m ocr_vision                      # print the recipe + default prompt
    python -m ocr_vision --list               # list scans in the current dir
    python -m ocr_vision --list /path/to/dir  # list scans in a directory
    python -m ocr_vision --prompts            # list available prompts
    python -m ocr_vision --prompt             # print the default prompt
    python -m ocr_vision --prompt questions   # print the question-corpus prompt
"""

import argparse
import sys
from pathlib import Path

SCAN_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".bmp"}

_HERE = Path(__file__).resolve().parent
PROMPTS_DIR = _HERE / "prompts"
WORKFLOW_PATH = _HERE / "WORKFLOW.md"

# name -> file, one-line description
PROMPTS = {
    "scan": ("scan_to_markdown.md", "single document -> one .md"),
    "questions": (
        "scanned_questions_to_markdown.md",
        "question corpus with TOC -> per-file .md tree + INDEX.md",
    ),
}
DEFAULT_PROMPT = "scan"

RECIPE = """\
Scan -> Markdown via MCP (local + remote backends)
==================================================

Local  backend: macos-vision-mcp  (Apple Vision, offline, no key, no egress)
Remote backend: mineru-mcp        (MinerU cloud, uploads to mineru.net)

Prompt: prompts/scan_to_markdown.md
Recipe: WORKFLOW.md

Steps
-----
1. Locate the file          file_search: **/<name>*
2. Run OCR (local)          mcp_macos-vision-_analyze_document(path=<abs path>)
                            (or _ocr_image for text only)
   Run OCR (remote)         mcp_mineru_sota_p_parse_documents(file_sources=[...])
3. Read the result          read_file the returned temp file
                            grep '"page": N|totalTextBlocks' for boundaries
4. Triage confidence        any textBlock confidence < 1.0 is suspect
                            cross-check against labels / barcode values
5. Format to Markdown       apply prompts/scan_to_markdown.md
6. Verify with the user     show the first 10 lines
7. Save                     write {same_stem}.md next to the source

Choosing a backend
------------------
Sensitive / PII scans     -> local (macOS Vision); never leaves the machine
Dense tables, formulas    -> remote (MinerU); stronger layout handling
Critical field accuracy   -> run both and diff; errors are uncorrelated

MCP tools
---------
Local:  analyze_document  OCR + faces + barcodes + rectangles  (primary)
        ocr_image         OCR only: format="text" | "blocks"   (faster)
Remote: parse_documents   PDF/Office/image/URL -> Markdown     (uploads)

See WORKFLOW.md for the full transcript and reference runs.
"""


def print_recipe(include_prompt: bool = True, prompt_name: str = DEFAULT_PROMPT) -> None:
    """Print the workflow recipe, optionally followed by a formatting prompt."""
    print(RECIPE)
    if include_prompt:
        print("-" * 60)
        print(f"Prompt: {prompt_name} ({PROMPTS[prompt_name][0]})")
        print("-" * 60)
        print(read_prompt(prompt_name))


def read_prompt(name: str = DEFAULT_PROMPT) -> str:
    """Return the contents of a named prompt, or a notice if missing.

    Args:
        name: Key into PROMPTS (e.g. "scan", "questions").
    """
    if name not in PROMPTS:
        return f"(unknown prompt {name!r}; choose from: {', '.join(PROMPTS)})"
    path = PROMPTS_DIR / PROMPTS[name][0]
    if not path.exists():
        return f"(prompt file not found: {path})"
    return path.read_text(encoding="utf-8").strip()


def list_scans(directory: Path) -> list[Path]:
    """Return scannable files in *directory*, sorted by name.

    Args:
        directory: Directory to search (non-recursive).

    Returns:
        Sorted list of paths whose suffix is a known scan format.
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    scans = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in SCAN_SUFFIXES
    )
    return scans


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan -> Markdown workflow helper (macOS Vision MCP).",
    )
    parser.add_argument(
        "--list", "-l", nargs="?", const=".", default=None,
        metavar="DIR",
        help="List scannable files in DIR (default: current directory).",
    )
    parser.add_argument(
        "--prompt", "-p", nargs="?", const=DEFAULT_PROMPT, default=None,
        choices=list(PROMPTS),
        help=(
            "Print a formatting prompt and exit. "
            f"Choices: {', '.join(PROMPTS)} (default: {DEFAULT_PROMPT})."
        ),
    )
    parser.add_argument(
        "--prompts", action="store_true",
        help="List available prompts.",
    )
    args = parser.parse_args()

    try:
        if args.prompts:
            print("Available prompts:\n")
            for name, (filename, desc) in PROMPTS.items():
                print(f"  {name:<12} {filename}")
                print(f"  {'':<12} {desc}\n")
            return

        if args.prompt is not None:
            print(read_prompt(args.prompt))
            return

        if args.list is not None:
            directory = Path(args.list).expanduser().resolve()
            scans = list_scans(directory)
            if not scans:
                print(f"No scannable files in {directory}")
                return
            print(f"Scannable files in {directory}:\n")
            for p in scans:
                size_kb = p.stat().st_size / 1024
                print(f"  {p.name:<40} {size_kb:8.1f} KB")
            print(f"\n{len(scans)} file(s). Process with analyze_document.")
            return

        print_recipe()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
