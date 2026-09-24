# watermark_remove — DeepSeek Vision watermark detection & removal

Self-contained tool that locates and removes watermarks from images using the
DeepSeek multimodal model (`deepseek-v4-flash-vision-exp`) for **detection** and
a separate reconstruction model for **removal**.

> **Note on the model:** `deepseek-v4-flash-vision-exp` is
> **understanding-only** — it accepts image input and returns text/JSON, but it
> cannot generate or edit images. So the flow is API-driven for *locating*
> watermarks, while the pixel *reconstruction* is done locally (OpenCV/LaMa).

## How it works

1. **Locate** (DeepSeek Vision) — the multimodal model analyzes the image and,
   for each watermark, returns a **tight bounding box**, a list of **`masks`**
   (small polygons, one per glyph/character, tracing the actual watermark
   shape), a **background description**, and an **opacity estimate**. It
   supports **targeted** detection (only match the watermarks you describe) or
   **untargeted** detection (find everything).
2. **Remove / reconstruct** (separate model) — the `masks` (or bbox fallback)
   become a binary mask, and a reconstruction model fills in the underlying
   pixels. See [Reconstruction models](#reconstruction-models) below.
3. **Artifacts** — optional auxiliary outputs: `regions.json`, `mask.png`,
   `mask_refined.png`, and per-region crops for review.

### Why glyph-level `masks` matter (avoiding over-erase)

The quality of inpainting is gated entirely by the mask. A single bounding box —
or even a coarse polygon — around a diagonal text watermark swallows background
and produces smeared results. So DeepSeek is asked to return **one small polygon
per glyph/character** (`masks`), hugging the visible watermark pixels. This
dramatically shrinks the erased area (e.g. the diagonal watermark's mask dropped
from ~100% of its bbox to ~45%).

Two optional mask refinements further prevent over-erase:

- `--refine-color` — refine the mask to keep only pixels that differ from the
  local background, using either `adaptive` (per-region foreground/background
  contrast, default) or `median` (single dominant color) strategy.

The **background** description and **opacity** estimate additionally steer the
reconstructor (e.g. tuning the inpainting radius).

### Reconstruction models

The DeepSeek Vision model **only locates** — it never edits pixels. The actual
pixel reconstruction is done by a dedicated inpainting model, chosen with
`--reconstructor`:

| Reconstructor | Model | When to use |
|---------------|-------|-------------|
| `opencv` (default) | OpenCV Telea inpainting | Small watermarks on textured backgrounds; deterministic, no GPU, instant |
| `lama` | LaMa (transformer inpainting) | Large or complex regions; synthesizes plausible content, needs `torch` |

```bash
# Deterministic (default)
python -m watermark_remove.main -i in.jpg -o out.jpg

# Deep reconstruction (requires requirements-lama.txt)
python -m watermark_remove.main -i in.jpg -o out.jpg --reconstructor lama
```

## Setup

```bash
cd watermark_remove
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional: for deep (LaMa) reconstruction
pip install -r requirements-lama.txt
```

Copy `.env.example` to `.env`:

```
DEEPSEEK_API_KEY=your_key
```

## Usage

```bash
# Remove ALL detected watermarks
python -m watermark_remove.main -i inputs/photo.jpg -o outputs/clean.jpg

# Remove ONLY the specified watermark(s) — ignore everything else
python -m watermark_remove.main -i inputs/photo.jpg -o outputs/clean.jpg \
    --watermark "bottom-right logo" --watermark "top-left timestamp"

# Keep auxiliary artifacts (mask + crops)
python -m watermark_remove.main -i inputs/photo.jpg -o outputs/clean.jpg \
    --keep-artifacts

# Detection only (no pixel changes)
python -m watermark_remove.main -i inputs/photo.jpg -o outputs/clean.jpg \
    --no-remove
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | — | Input image path |
| `--output, -o` | — | Output image path |
| `--watermark, -w` | none | Watermark description to target (repeatable). If omitted, ALL watermarks are removed |
| `--reconstructor, -r` | `opencv` | Reconstruction model: `opencv` or `lama` |
| `--radius` | `5` | Inpainting radius (opencv reconstructor only) |
| `--refine-color` | off | Refine mask to watermark color (avoids over-erasing background) |
| `--refine-mode` | `adaptive` | Refinement strategy: `adaptive` or `median` |
| `--color-tol` | `60` | Color distance tolerance for refinement |
| `--verify` | off | After removal, ask DeepSeek to verify + iterate on residue |
| `--max-iters` | `3` | Max refine iterations when `--verify` is set |
| `--keep-artifacts` | off | Save mask + region crops to `artifacts/` |
| `--artifacts-dir` | `artifacts` | Directory for auxiliary artifacts |
| `--no-remove` | off | Locate only, skip inpainting |

## Files

```
watermark_remove/
├── __init__.py          # package marker
├── main.py              # CLI: python -m watermark_remove.main
├── llm.py               # DeepSeek Vision client + locate_watermarks
├── remove.py            # reconstruction (opencv / lama) + artifact helpers
├── config.py            # .env loading
├── prompts/
│   └── locate_watermark.md
├── inputs/              # drop sample pictures here (gitignored)
├── outputs/             # cleaned images (gitignored)
├── artifacts/           # regions.json, mask.png, crops (gitignored)
├── requirements.txt
├── requirements-lama.txt  # optional deep-reconstruction extras
├── .env.example
└── README.md
```

## Notes

- The model id is configurable via `DEEPSEEK_VISION_MODEL` (default
  `deepseek-v4-flash-vision-exp`) in case the name changes.
- `inputs/`, `outputs/`, and `artifacts/` are gitignored (only `.gitkeep` is
  tracked), so your sample pictures won't be committed.
