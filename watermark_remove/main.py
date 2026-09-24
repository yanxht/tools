"""CLI for watermark removal.

Usage:
    # Remove ALL detected watermarks
    python -m watermark_remove.main -i inputs/photo.jpg -o outputs/clean.jpg

    # Remove ONLY the specified watermark(s) — ignore everything else
    python -m watermark_remove.main -i inputs/photo.jpg -o outputs/clean.jpg \\
        --watermark "bottom-right logo" --watermark "top-left timestamp"

    # Keep auxiliary artifacts (mask + crops)
    python -m watermark_remove.main -i inputs/photo.jpg -o outputs/clean.jpg \\
        --keep-artifacts
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

from . import config
from .llm import (locate_watermarks, locate_watermarks_consensus, verify_removal,
                  evaluate_quality, refine_region)
from .remove import inpaint, save_artifacts

# Tool directory (absolute), so default artifact paths resolve relative to the
# tool regardless of the caller's current working directory.
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_image(path: str):
    data = open(path, "rb").read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return data, img


def main(argv=None):
    parser = argparse.ArgumentParser(description="Remove watermarks via DeepSeek Vision.")
    parser.add_argument("--input", "-i", required=True, help="Input image path")
    parser.add_argument("--output", "-o", required=True, help="Output image path")
    parser.add_argument("--watermark", "-w", action="append", default=None,
                        help="Watermark description to target (repeatable). "
                             "If omitted, ALL detected watermarks are removed.")
    parser.add_argument("--reconstructor", "-r", default="opencv",
                        choices=["opencv", "lama"],
                        help="Reconstruction model: 'opencv' (deterministic "
                             "inpainting) or 'lama' (deep transformer). "
                             "Default: opencv")
    parser.add_argument("--radius", type=int, default=5,
                        help="Inpainting radius for the opencv reconstructor")
    parser.add_argument("--refine-color", action="store_true",
                        help="Refine the mask to keep only pixels matching the "
                             "watermark's color (avoids over-erasing "
                             "background that a coarse polygon overlaps)")
    parser.add_argument("--color-tol", type=int, default=60,
                        help="Color distance tolerance for --refine-color")
    parser.add_argument("--refine-mode", default="adaptive",
                        choices=["adaptive", "median"],
                        help="Mask refinement strategy: 'adaptive' (per-region "
                             "foreground/background contrast, default) or "
                             "'median' (single dominant color)")
    parser.add_argument("--segment", action="store_true",
                        help="Build the mask by deterministically segmenting the "
                             "watermark pixels from the image (robust to model "
                             "color/position hallucinations), instead of using "
                             "the model's polygon/masks")
    parser.add_argument("--contrast-thresh", type=float, default=0.15,
                        help="Contrast threshold for --segment (lower = more "
                             "aggressive)")
    parser.add_argument("--fill-hollow", action="store_true",
                        help="Reconnect hollow/outlined watermark strokes into "
                             "solid glyph shapes (dilate + close) before "
                             "inpainting — mimics tracing each letter's outline")
    parser.add_argument("--refine", action="store_true",
                        help="Tighten each detected region's bbox with a "
                             "crop-and-re-localize pass (removes confusing "
                             "context for more precise boxes)")
    parser.add_argument("--keep-artifacts", action="store_true",
                        help="Save mask + region crops to artifacts/")
    parser.add_argument("--artifacts-dir", default="artifacts",
                        help="Directory for auxiliary artifacts (default: artifacts/)")
    parser.add_argument("--no-remove", action="store_true",
                        help="Only locate watermarks, skip inpainting")
    parser.add_argument("--verify", action="store_true",
                        help="After removal, ask DeepSeek to verify cleanup and "
                             "iterate (up to --max-iters) if residue remains")
    parser.add_argument("--max-iters", type=int, default=3,
                        help="Max refine iterations when --verify is set")
    parser.add_argument("--evaluate", action="store_true",
                        help="After removal, pass input+output to DeepSeek to "
                             "score the result and critique the quality")
    parser.add_argument("--consensus", type=int, default=1,
                        help="Run localization this many times and merge "
                             "results (default 1; 3+ reduces non-determinism)")
    args = parser.parse_args(argv)

    if not config.DEEPSEEK_API_KEY:
        sys.exit("DEEPSEEK_API_KEY not set. Copy .env.example to .env and fill it in.")

    # Resolve artifact dir relative to the tool dir when a bare name is given.
    artifacts_dir = args.artifacts_dir
    if not os.path.isabs(artifacts_dir):
        artifacts_dir = os.path.join(TOOL_DIR, artifacts_dir)

    image_bytes, img = _load_image(args.input)

    if args.watermark:
        print(f"Locating target watermark(s): {', '.join(args.watermark)} ...")
    else:
        print(f"Locating all watermarks in {args.input} ...")

    if args.consensus > 1:
        regions = locate_watermarks_consensus(
            image_bytes, args.watermark,
            config.DEEPSEEK_API_KEY, config.DEEPSEEK_BASE_URL, config.DEEPSEEK_VISION_MODEL,
            runs=args.consensus,
        )
    else:
        regions = locate_watermarks(
            image_bytes, args.watermark,
            config.DEEPSEEK_API_KEY, config.DEEPSEEK_BASE_URL, config.DEEPSEEK_VISION_MODEL,
        )

    # Optional crop-and-re-localize pass to tighten each region's bbox.
    if args.refine and regions:
        print("Refining region bounding boxes (crop + re-localize) ...")
        refined_regions = []
        for r in regions:
            bbox = r.get("bbox")
            if not bbox or len(bbox) != 4:
                refined_regions.append(r)
                continue
            rr = refine_region(
                image_bytes, bbox,
                config.DEEPSEEK_API_KEY, config.DEEPSEEK_BASE_URL, config.DEEPSEEK_VISION_MODEL,
            )
            if rr and rr.get("bbox"):
                print(f"  {r.get('label','?')}: {[round(v,3) for v in bbox]} -> "
                      f"{[round(v,3) for v in rr['bbox']]}")
                refined_regions.append(rr)
            else:
                print(f"  {r.get('label','?')}: refine found nothing, keeping original")
                refined_regions.append(r)
        regions = refined_regions

    if not regions:
        print("No matching watermarks detected — output will be a copy of the input.")
    else:
        print(f"Detected {len(regions)} region(s):")
        for r in regions:
            extra = []
            if r.get("background"):
                extra.append(f"bg={r['background']}")
            if r.get("opacity") is not None:
                extra.append(f"opacity={r['opacity']:.2f}")
            if r.get("polygon"):
                extra.append(f"polygon({len(r['polygon'])}pts)")
            suffix = f" [{', '.join(extra)}]" if extra else ""
            print(f"  - {r.get('label', '?')} (conf={r.get('confidence', '?')}) "
                  f"bbox={r.get('bbox')}{suffix}")

    # Always emit the detection JSON as an auxiliary artifact.
    os.makedirs(artifacts_dir, exist_ok=True)
    with open(os.path.join(artifacts_dir, "regions.json"), "w", encoding="utf-8") as f:
        json.dump({"regions": regions, "targets": args.watermark}, f, indent=2)

    if args.no_remove:
        print(f"Detection only. Regions written to {artifacts_dir}/regions.json")
        return 0

    result = inpaint(img, regions, radius=args.radius, reconstructor=args.reconstructor,
                     refine_color=args.refine_color, color_tol=args.color_tol,
                     refine_mode=args.refine_mode, segment=args.segment,
                     contrast_thresh=args.contrast_thresh, fill_hollow=args.fill_hollow)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    cv2.imwrite(args.output, result)
    print(f"Wrote cleaned image to {args.output} (reconstructor={args.reconstructor})")

    if args.keep_artifacts:
        save_artifacts(img, regions, artifacts_dir,
                       refine_color=args.refine_color, color_tol=args.color_tol,
                       refine_mode=args.refine_mode)
        print(f"Auxiliary artifacts saved to {artifacts_dir}/")

    # Optional verification + iterative refinement.
    if args.verify:
        result = _verify_and_refine(
            result, args.output, artifacts_dir,
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            model=config.DEEPSEEK_VISION_MODEL,
            radius=args.radius,
            reconstructor=args.reconstructor,
            max_iters=args.max_iters,
            refine_color=args.refine_color,
            color_tol=args.color_tol,
            refine_mode=args.refine_mode,
        )

    # Optional quality evaluation (input vs output).
    if args.evaluate:
        _evaluate(image_bytes, args.output, artifacts_dir)

    return 0


def _evaluate(input_bytes, output_path, artifacts_dir):
    """Ask DeepSeek to compare input vs output and report removal quality."""
    ok, out_buf = cv2.imencode(".jpg", cv2.imread(output_path))
    if not ok:
        print("Quality evaluation skipped: could not read output image.")
        return
    print("Evaluating quality (input vs output) ...")
    report = evaluate_quality(
        input_bytes, out_buf.tobytes(),
        config.DEEPSEEK_API_KEY, config.DEEPSEEK_BASE_URL, config.DEEPSEEK_VISION_MODEL,
    )
    print(f"  score: {report.get('score')}/10")
    print(f"  watermark_removed: {report.get('watermark_removed')}")
    print(f"  content_damaged: {report.get('content_damaged')}")
    if report.get("residue"):
        print(f"  residue: {report['residue']}")
    if report.get("artifacts"):
        print(f"  artifacts: {report['artifacts']}")
    if report.get("notes"):
        print(f"  notes: {report['notes']}")

    os.makedirs(artifacts_dir, exist_ok=True)
    with open(os.path.join(artifacts_dir, "quality_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Quality report written to {artifacts_dir}/quality_report.json")


def _verify_and_refine(result, output_path, artifacts_dir, *, api_key, base_url,
                       model, radius, reconstructor, max_iters, refine_color=False,
                       color_tol=60, refine_mode="adaptive", min_conf=0.6,
                       min_area=0.0005):
    """Iteratively ask DeepSeek to check the cleaned image and re-inpaint any
    leftover residue, up to `max_iters` rounds.

    Guards against non-convergence:
    - Ignores leftover regions below `min_conf` confidence or `min_area`
      (normalized) — filters out hallucinated faint residue.
    - Stops early if the leftover region overlaps heavily (IoU > 0.8) with the
      previous round's region, meaning we're not making progress.
    """
    prev_bboxes = []
    for it in range(1, max_iters + 1):
        ok, buf = cv2.imencode(".jpg", result)
        if not ok:
            break
        check = verify_removal(buf.tobytes(), api_key, base_url, model)
        remaining = check.get("remaining", [])

        # Filter to confident, non-trivial regions.
        kept = []
        for r in remaining:
            conf = r.get("confidence", 1.0)
            bbox = r.get("bbox")
            if conf is None or conf < min_conf:
                continue
            if bbox and len(bbox) == 4:
                area = bbox[2] * bbox[3]
                if area < min_area:
                    continue
            kept.append(r)
        remaining = kept

        if check.get("clean") or not remaining:
            print(f"Verification pass {it}: clean ✓")
            break

        # Detect non-progress: if every leftover bbox ~= a previous one, stop.
        if prev_bboxes and all(
            any(_iou(r.get("bbox"), p) > 0.8 for p in prev_bboxes)
            for r in remaining
        ):
            print(f"Verification pass {it}: no progress (same regions) — stopping.")
            break

        print(f"Verification pass {it}: {len(remaining)} leftover region(s) found, re-inpainting ...")
        for r in remaining:
            print(f"    - {r.get('label', '?')} conf={r.get('confidence')} bbox={r.get('bbox')}")
        result = inpaint(result, remaining, radius=radius, reconstructor=reconstructor,
                         refine_color=refine_color, color_tol=color_tol,
                         refine_mode=refine_mode)
        cv2.imwrite(output_path, result)
        print(f"    updated {output_path}")
        prev_bboxes = [r.get("bbox") for r in remaining if r.get("bbox")]
    else:
        print(f"Verification reached max iterations ({max_iters}); stopping.")
    return result


def _iou(a, b):
    """Intersection-over-Union of two [x, y, w, h] boxes (normalized or px)."""
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0.0
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
