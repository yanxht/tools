# ocr_vision

Turn scanned PDFs / images into clean Markdown. Two **fully independent**
backends: a local one (macOS Vision, via `macos-vision-mcp`) and a remote one
(MinerU, via `mineru-mcp`). Pick one, or run both and diff.

| Backend | Engine | Cost | Where it runs | Data egress | Best for |
|---------|--------|------|---------------|-------------|----------|
| **macOS Vision** (default) | Apple Vision via `macos-vision-mcp` | $0 | Local (this Mac) | **None** — offline | PII / sensitive scans; no key; ID & form layouts |
| **MinerU** | MinerU cloud via `mineru-mcp` | Free (Flash) / paid w/ token | Remote (mineru.net) | **Uploads the file** | Scanned tables, formulas, multi-column; 200-page docs |

> **Direction:** scanned document (PDF/image) → clean Markdown
> **Driver:** an AI agent (VS Code Copilot) calling the MCP tools
> **Local backend:** macOS Vision via `macos-vision-mcp` (offline, no key)
> **Remote backend:** MinerU via `mineru-mcp` (uploads to mineru.net)

This tool captures the *prompt and process* of the OCR workflow, not a
reimplementation of either OCR engine. The heavy lifting is done by the MCP
servers. What this directory preserves is the **repeatable recipe**: which tool
to call, in what order, how to read the result, and how to turn raw OCR blocks
into clean Markdown.

## Backend parity

Both backends take the same input (a scan) and produce the same output (clean
Markdown), so they are swappable. They differ in **where the data goes** and in
**which errors they make** — and their errors are largely *uncorrelated*, which
makes running both a genuine cross-check rather than redundancy.

Observed on `EAD_card_stemopt.pdf` (an EAD card):

| Field | macOS Vision | MinerU | Truth |
|-------|--------------|--------|-------|
| Given Name | XIAOHAN | IAOHAN | XIAOHAN |
| Category | `СОЗС` (conf. 0.3) | C03C | C03C |
| USCIS# | 11-660-486 | 111-660-486 | 11-660-486 |
| Card# | YSC1990261342 | YSC1990261342 | YSC1990261342 |
| MRZ line 1 | ...YSC1990261342 | ...YS**0**1990261342 | ...YSC1990261342 |

Each engine won on fields the other lost. For high-stakes fields (names, ID
numbers), diff the two rather than trusting either alone.

### Choosing a backend

- **Sensitive documents (IDs, certificates, anything with PII):** use macOS
  Vision. It never leaves the machine.
- **Dense tables, formulas, multi-column academic PDFs:** MinerU is stronger,
  and supports up to 200 pages/file with an API token.
- **Maximum accuracy on a critical field:** run both, diff, and reconcile by
  hand. This is the only mode that catches a *confident* misread.

## Why MCP (and not a Python OCR library)

Apple's Vision OCR is excellent at scanned documents (IDs, certificates, forms)
and runs locally with no cloud round-trip. The MCP server exposes it to the
agent, so the "tool" here is a documented agent workflow plus a prompt template,
not a standalone binary.

## The workflow

```
scan.pdf ──analyze_document──▶ JSON (paragraphs + textBlocks + bboxes)
                                     │
                                     ├─ paragraphs[]  → reading-order text  ← primary surface
                                     └─ textBlocks[]  → per-line text + confidence + bbox
                                     │
                                     ▼
                          prompts/scan_to_markdown.md   ← cleanup rules
                                     │
                                     ▼
                              scan.md  (clean Markdown)
```

### Step by step

1. **Locate the file.** Use `file_search` to confirm the exact path of the scan.
2. **Run OCR.** Call `analyze_document` with the absolute path. It returns, per
   page: `paragraphs[]` (reading order — use this as the primary text surface),
   `textBlocks[]` (per-line text with `confidence` and `bbox`), plus any
   `faces`, `barcodes`, and `rectangles`.
   - For text-only needs, `ocr_image` is cheaper. Use `format="blocks"` when you
     need bounding boxes, `format="text"` for plain reading-order text.
3. **Read the result.** Large results are written to a temp file — read it with
   `read_file`, or grep the tail for `"page": N` / `totalTextBlocks` to find
   page boundaries and the summary.
4. **Triage confidence.** Any `textBlock` with `confidence < 1.0` is suspect.
   Cross-check low-confidence blocks against neighboring high-confidence ones
   (e.g. a label, or a barcode value) before trusting them.
5. **Format to Markdown** using `prompts/scan_to_markdown.md`.
6. **Show the first 10 lines** to the user for a quality check.
7. **Save** as `{same_name}.md` next to the source.

## Files

```
ocr_vision/
├── README.md                      # this file
├── __init__.py                    # package marker
├── __main__.py                    # helper: locate scans + emit the agent recipe
├── prompts/
│   ├── scan_to_markdown.md        # single-document cleanup/formatting prompt
│   └── scanned_questions_to_markdown.md  # multi-question corpus -> per-file Markdown
└── WORKFLOW.md                    # the full agent transcript recipe (copy-paste)
```

## Prompts

| Prompt | Use when | Output |
|--------|----------|--------|
| [`scan_to_markdown.md`](prompts/scan_to_markdown.md) | One document (ID, certificate, form) | A single `.md` mirroring the document |
| [`scanned_questions_to_markdown.md`](prompts/scanned_questions_to_markdown.md) | A corpus of printed questions with a TOC | One `.md` per question, in a TOC-derived folder tree, plus `INDEX.md` |

### `scanned_questions_to_markdown.md`

Structures a scanned question bank into a browsable Markdown tree. Its governing
rule is **the TOC is the schema**:

- **Structure is never inferred.** Categories, titles, and numbering come from
  the document's own table of contents, verbatim.
- **Characters may be corrected.** OCR glyph misreads are repaired, but every
  correction is logged in a `<!-- OCR corrections -->` block and in the report.

That split is the point: an absolute "no inference" rule would forbid the
character repairs OCR actually needs, while a loose rule would let the agent
invent categories. The prompt separates the two.

It also enforces a TOC quality gate before any files are written, a six-check
validation pass (coverage, orphans, structure, frontmatter, links, titles),
batched execution with a resumable checkpoint, and idempotent re-runs.


## Usage

The real driver is the agent. This package provides a helper that prints the
exact recipe and lists candidate scans:

```bash
# Show the workflow recipe + the prompt
python -m ocr_vision

# List scanned candidates in a directory
python -m ocr_vision --list /path/to/test_OCR
```

Then, in the agent, follow `WORKFLOW.md` verbatim, using
`prompts/scan_to_markdown.md` for the formatting step.

## MCP tools used

**Local backend (`macos-vision-mcp`):**

| Tool | Purpose |
|------|---------|
| `analyze_document` | Full pipeline: OCR + faces + barcodes + rectangles. **Primary.** |
| `ocr_image` | OCR only (text or blocks). Faster when you don't need detection. |
| `find_element` / `assert_text` | Only for on-screen UI, not document scans. |

**Remote backend (`mineru-mcp`):**

| Tool | Purpose |
|------|---------|
| `parse_documents` | PDF/Office/image/URL → Markdown. Uploads to mineru.net. |
| `get_ocr_languages` | List supported OCR language codes. |

## Requirements

- macOS (Apple Vision framework) — for the local backend
- The `macos-vision-mcp` server enabled in the MCP client (local backend)
- The `mineru-mcp` server enabled in the MCP client (remote backend)
- No Python dependencies (the helper uses only the stdlib)

## Notes

- **Reading order matters.** Prefer `paragraphs[].text` over concatenating
  `textBlocks[]`; the former is already grouped in reading order.
- **Confidence is your QA signal.** Blocks at `1.0` are reliable; below that,
  verify. Seals, watermarks, security print, and handwriting are the usual
  culprits.
- **Corrections are the model's job, not the engine's.** No OCR engine repairs
  its own output; it reports text plus a confidence score. The AI model does the
  interpreting (e.g. `ISCIS#` → `USCIS#`, `СОЗС` → `C03C`) using domain and
  format knowledge. That step is non-deterministic.
- **Keep the raw artifacts.** When a value is corrected, note the raw OCR string
  in an "OCR Notes" section so a human can re-verify against the original.
- **Barcodes are a cross-check.** A Code39 barcode value often duplicates a
  printed file number — use it to validate the OCR of that number.
- **Mind the egress.** The local backend never sends the file anywhere. The
  remote backend uploads it to mineru.net — do not use it for data that must
  stay on-device.

