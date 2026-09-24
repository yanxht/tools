"""PDF to JPG converter — convert each page of a PDF into a JPG image.

Uses PyMuPDF (fitz) for rendering — no system dependencies needed.

Usage:
    python -m pdf_jpg input.pdf              # output to input_jpg/ folder
    python -m pdf_jpg input.pdf -o outdir/   # custom output directory
    python -m pdf_jpg input.pdf --dpi 200    # set DPI (default: 150)
    python -m pdf_jpg input.pdf -q 85        # JPEG quality (default: 92)
"""

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF


def pdf_to_jpg(
    pdf_path: Path,
    output_dir: Path | None = None,
    dpi: int = 150,
    quality: int = 92,
) -> list[Path]:
    """Convert each page of a PDF into a JPG file.

    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Directory to save JPG files. Defaults to {pdf_stem}_jpg/.
        dpi: Resolution in dots per inch (default 150).
        quality: JPEG compression quality 1–100 (default 92).

    Returns:
        List of paths to the generated JPG files.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if output_dir is None:
        output_dir = pdf_path.parent / f"{pdf_path.stem}_jpg"

    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72.0  # PDF default is 72 DPI
    mat = fitz.Matrix(zoom, zoom)

    saved: list[Path] = []
    total = len(doc)

    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat)
        out_path = output_dir / f"{pdf_path.stem}_p{i:03d}.jpg"
        pix.pil_save(str(out_path), format="JPEG", quality=quality)
        saved.append(out_path)
        print(f"  [{i}/{total}] {out_path.name}")

    doc.close()
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert PDF pages to JPG images.",
    )
    parser.add_argument("pdf", type=Path, help="Path to input PDF file")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output directory (default: {pdf_name}_jpg/)",
    )
    parser.add_argument(
        "--dpi", type=int, default=150,
        help="Resolution in DPI (default: 150)",
    )
    parser.add_argument(
        "-q", "--quality", type=int, default=92,
        help="JPEG quality 1–100 (default: 92)",
    )
    args = parser.parse_args()

    try:
        out_paths = pdf_to_jpg(
            pdf_path=args.pdf,
            output_dir=args.output,
            dpi=args.dpi,
            quality=args.quality,
        )
        print(f"\nDone — {len(out_paths)} pages saved to {out_paths[0].parent}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
