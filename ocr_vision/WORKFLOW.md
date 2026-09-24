# WORKFLOW — Scan → Markdown with macOS Vision MCP

This is the exact recipe used to convert a scanned PDF into clean Markdown.
It is written as an agent transcript so it can be replayed verbatim.

**Engine:** `macos-vision-mcp` (Apple Vision, local/offline, no API key)
**Prompt:** [`prompts/scan_to_markdown.md`](prompts/scan_to_markdown.md)

---

## 0. The user prompt

The request that drives this workflow, in its canonical form:

> Please use the `macos-vision-mcp` tools to process the scanned document
> `<file>.pdf`. Steps:
> 1. Use `analyze_document` or `ocr_image` to perform a local OCR on the scan.
> 2. Extract the text in reading order and format it into clean Markdown.
> 3. Show the first 10 lines in chat so I can verify OCR quality.
> 4. If quality looks good, save the full Markdown as `<file>.md`.

---

## 1. Locate the file

```
file_search: **/test_OCR/**
```

Confirm the absolute path. Never guess it.

## 2. Run OCR

```
mcp_macos-vision-_analyze_document:
    path: /absolute/path/to/scan.pdf
```

- Use `analyze_document` when you want OCR **plus** faces/barcodes/rectangles.
- Use `mcp_macos-vision-_ocr_image` instead for text only:
  - `format: "text"`   → plain reading-order string
  - `format: "blocks"` → per-line text with bboxes + confidence

Large results are written to a temp file and the tool returns its path.

### 2b. Alternate backend — MinerU (remote)

For dense tables, formulas, or multi-column documents, MinerU is often
stronger. It **uploads the file to mineru.net**, so do not use it for data that
must stay on-device.

```
mcp_mineru_sota_p_parse_documents:
    file_sources: ["/absolute/path/to/scan.pdf"]
```

Returns Markdown directly (no confidence scores). Because the two backends make
*uncorrelated* errors, running both and diffing is a genuine cross-check. On
`EAD_card_stemopt.pdf`, MinerU read the category code `C03C` correctly where
Vision produced `СОЗС`, while Vision read `XIAOHAN` and `11-660-486` correctly
where MinerU produced `IAOHAN` and `111-660-486`.


## 3. Read the result

Read the returned temp file. For big documents, jump to the interesting parts:

```bash
# find page boundaries + summary
grep -n '"page": 1\|totalTextBlocks\|totalParagraphs\|totalFaces\|totalBarcodes\|totalRectangles' <result>.json

# find a detected barcode value
grep -n -A5 '"barcodes"' <result>.json
```

Then `read_file` the ranges you need.

## 4. Triage confidence

Scan `textBlocks[]` for `"confidence"` values below `1.0`. Typical culprits:

| Symptom | Cause |
|---------|-------|
| Confused letters (`ISCIS#` for `USCIS#`) | stylized / small font |
| Cyrillic-looking garbage (`СОЗС` for `C03C`) | font ligatures / kerning |
| Fragments (`ECISTRAR`) | watermark or seal overprint |
| Odd dates (`1J/3/16`) | handwriting or stamp |
| `CARTOISEA`, `(lau` | security print / seal noise |

Cross-check against a high-confidence neighbor (a label, a duplicate barcode
value) before correcting.

## 5. Format to Markdown

Apply [`prompts/scan_to_markdown.md`](prompts/scan_to_markdown.md). Key moves:

- `paragraphs[]` → reading order
- label/value pairs → tables, grouped under `###` headings
- low-confidence fixes → body, with raw string preserved in `## OCR Notes`
- MRZ / machine-readable → fenced `text` block
- one `## Page N` per page

## 6. Verify with the user

Show the **first 10 lines** of extracted text in chat. This is the quality gate:
if the top of the document reads correctly, the rest usually does too.

## 7. Save

Write `{same_stem}.md` next to the source PDF.

---

## Reference run

Input:  `EAD_card_stemopt.pdf` (2 pages, 35 text blocks)
Output: `EAD_card_stemopt.md`

Low-confidence items found and handled:

| Raw OCR | Conf. | Corrected | Reason |
|---------|-------|-----------|--------|
| `ISCIS#` | 0.5 | `USCIS#` | stylized label font |
| `СОЗС` | 0.3 | `C03C` | category code, font artifact |

Everything else read at confidence `1.0` (name, dates, card number, MRZ).

Second reference run: `birth_certificate.pdf` (2 pages, 151 text blocks,
1 Code39 barcode). The barcode value `131201600090761` matched the printed
State File Number `131-2016-00090761`, confirming that field's OCR.
