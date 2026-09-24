"""Batch runner: process all images in inputs/ through the watermark removal flow.

Usage:
    python -m watermark_remove.batch [--verify] [--reconstructor opencv|lama]
"""
import argparse
import os
import sys
import time

from . import config
from .main import main as _run_single

INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inputs")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


def _image_files(directory):
    exts = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    return sorted(
        f for f in os.listdir(directory)
        if f.lower().endswith(exts) and not f.startswith(".")
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Batch watermark removal.")
    parser.add_argument("--verify", action="store_true", help="Run verification loop")
    parser.add_argument("--reconstructor", "-r", default="opencv", choices=["opencv", "lama"])
    parser.add_argument("--keep-artifacts", action="store_true")
    parser.add_argument("--refine-color", action="store_true",
                        help="Refine mask to watermark color (avoids over-erasing)")
    parser.add_argument("--refine-mode", default="adaptive", choices=["adaptive", "median"])
    parser.add_argument("--color-tol", type=int, default=60)
    args = parser.parse_args(argv)

    files = _image_files(INPUT_DIR)
    if not files:
        sys.exit(f"No images found in {INPUT_DIR}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Processing {len(files)} image(s) ...\n")

    for f in files:
        inp = os.path.join(INPUT_DIR, f)
        stem, ext = os.path.splitext(f)
        outp = os.path.join(OUTPUT_DIR, f"{stem}_clean{ext}")
        print(f"===== {f} =====")
        start = time.time()
        argv = ["--input", inp, "--output", outp,
                "--reconstructor", args.reconstructor,
                "--artifacts-dir", os.path.join(os.path.dirname(INPUT_DIR), "artifacts", stem)]
        if args.verify:
            argv += ["--verify"]
        if args.keep_artifacts:
            argv += ["--keep-artifacts"]
        if args.refine_color:
            argv += ["--refine-color", "--refine-mode", args.refine_mode,
                     "--color-tol", str(args.color_tol)]
        try:
            _run_single(argv)
        except Exception as e:
            print(f"  ERROR: {e}")
        print(f"  (took {time.time() - start:.1f}s)\n")

    print("Done.")


if __name__ == "__main__":
    raise SystemExit(main())
