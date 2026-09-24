"""Pixel-level watermark removal and image reconstruction.

The vision model supplies watermark regions, each with a tight bounding box, an
optional polygon outline (the actual watermark shape), a background description,
and an opacity estimate. This module converts them to a pixel mask and
reconstructs the underlying image.

Reconstruction models used:
- **OpenCV inpainting** (default, deterministic, no extra deps): Telea. Good for
  small watermarks on textured backgrounds.
- **LaMa deep inpainting** (optional, `--reconstructor lama`): a transformer
  inpainting model that synthesizes plausible content for larger/more complex
  regions. Requires the `torch` + `lama-cleaner` extras (see README).

This module also emits auxiliary artifacts (mask image, per-region crops) for
review.
"""
import os

import cv2
import numpy as np


def _denorm(bbox, width, height):
    x, y, w, h = bbox
    return int(x * width), int(y * height), int(w * width), int(h * height)


def _denorm_point(pt, width, height):
    x, y = pt
    return int(x * width), int(y * height)


def _region_polygon(region, width, height):
    """Return a list of (x, y) pixel points for a region's polygon, if present."""
    poly = region.get("polygon")
    if not poly or not isinstance(poly, list) or len(poly) < 3:
        return None
    pts = []
    for p in poly:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            pts.append(_denorm_point(p, width, height))
    return pts if len(pts) >= 3 else None


def _region_masks(region, width, height):
    """Return a list of polygons (each a list of (x, y) px points) for a region.

    Prefers the newer `masks` field (list of tight sub-polygons, one per glyph);
    falls back to the single `polygon` field.
    """
    masks = region.get("masks")
    if isinstance(masks, list) and masks:
        polys = []
        for m in masks:
            if not isinstance(m, list) or len(m) < 3:
                continue
            pts = []
            for p in m:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    pts.append(_denorm_point(p, width, height))
            if len(pts) >= 3:
                polys.append(pts)
        if polys:
            return polys
    single = _region_polygon(region, width, height)
    return [single] if single else []


def _draw_region_mask(mask, region, width, height, pad):
    """Draw a single region into the mask.

    Prefers the model's polygon/masks outlines (the actual watermark shape) so we
    erase ONLY the watermark glyphs, not the surrounding background. The bbox is
    used only as a fallback when no polygon is available.
    """
    polys = _region_masks(region, width, height)
    if polys:
        for pts in polys:
            arr = np.array(pts, dtype=np.int32)
            cv2.fillPoly(mask, [arr], 255)
        return

    # Fallback: no polygon — use a conservative bbox (tight, lightly padded).
    bbox = region.get("bbox", [0, 0, 0, 0])
    x, y, w, h = _denorm(bbox, width, height)
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(width, x + w + pad)
    y1 = min(height, y + h + pad)
    mask[y0:y1, x0:x1] = 255


def build_mask(width: int, height: int, regions: list[dict], pad: int = 8) -> np.ndarray:
    """Build a binary mask (255 = erase) from normalized regions.

    Prefers the model's polygon outline (tight, shape-accurate); falls back to a
    padded bbox when no polygon is available.
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    for region in regions:
        _draw_region_mask(mask, region, width, height, pad)
    # Dilate the mask so inpainting covers soft/anti-aliased edges.
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    return mask


def segment_watermark(image: np.ndarray, region: dict, pad: int = 8,
                      contrast_thresh: float = 0.15) -> np.ndarray:
    """Deterministically segment the watermark pixels inside a region's bbox.

    Does NOT rely on the model's (often misplaced) polygon/masks. Instead it
    finds, within the bbox, the pixels that differ strongly from the local
    background — i.e. the actual watermark glyphs, whatever their color (red,
    white, dark, etc.).

    Steps:
      1. Crop the (padded) bbox.
      2. Estimate the local background color as the median of the crop's border.
      3. Keep pixels whose color differs from that background by more than the
         threshold (in normalized RGB distance).
      4. Clean up with morphology.

    Returns a full-size mask (same shape as image) with 255 at watermark pixels.
    """
    height, width = image.shape[:2]
    bbox = region.get("bbox", [0, 0, 0, 0])
    x, y, w, h = _denorm(bbox, width, height)
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(width, x + w + pad)
    y1 = min(height, y + h + pad)

    if x1 - x0 < 4 or y1 - y0 < 4:
        return np.zeros((height, width), dtype=np.uint8)

    crop = image[y0:y1, x0:x1].astype(np.float32)

    # Estimate background from the crop's border ring.
    border = np.concatenate([
        crop[0, :, :], crop[-1, :, :], crop[:, 0, :], crop[:, -1, :]
    ], axis=0)
    bg = np.median(border, axis=0)  # [B, G, R]

    # Normalized color distance from background.
    diff = np.linalg.norm(crop - bg, axis=2)
    # Normalize by local intensity so dark/bright both work.
    intensity = np.linalg.norm(bg) + 1e-6
    ratio = diff / intensity

    fg = ratio > contrast_thresh

    # Morphological cleanup: close small gaps, remove tiny specks.
    fg_u8 = (fg * 255).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    fg_u8 = cv2.morphologyEx(fg_u8, cv2.MORPH_CLOSE, kernel, iterations=1)
    fg_u8 = cv2.morphologyEx(fg_u8, cv2.MORPH_OPEN, kernel, iterations=1)

    full = np.zeros((height, width), dtype=np.uint8)
    full[y0:y1, x0:x1] = fg_u8
    return full


def fill_hollow_strokes(mask: np.ndarray, dilate_iters: int = 2,
                        close_iters: int = 2) -> np.ndarray:
    """Reconnect hollow/outlined watermark strokes into solid glyph shapes.

    Hollow (outlined) text fragments under color thresholding into many small
    disconnected components. This mimics the human "trace the outline, then fill
    the enclosed area" approach: dilate to reconnect the stroke fragments, then
    close to fill the hollow interiors.

    Args:
        mask: Binary mask (255 = watermark pixels).
        dilate_iters: Dilation iterations to reconnect stroke fragments.
        close_iters: Closing iterations to fill hollow interiors.
    """
    if mask.sum() == 0:
        return mask
    kernel = np.ones((3, 3), np.uint8)
    out = cv2.dilate(mask, kernel, iterations=dilate_iters)
    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, kernel, iterations=close_iters)
    return out


def build_mask_deterministic(image: np.ndarray, regions: list[dict],
                             pad: int = 8, contrast_thresh: float = 0.15) -> np.ndarray:
    """Build a mask by deterministically segmenting watermark pixels.

    Uses `segment_watermark` per region (color-contrast vs local background),
    which is robust to the model's color/position hallucinations. Falls back to
    the polygon/bbox mask if segmentation finds nothing.
    """
    height, width = image.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    for region in regions:
        seg = segment_watermark(image, region, pad=pad, contrast_thresh=contrast_thresh)
        if seg.sum() > 0:
            mask = cv2.bitwise_or(mask, seg)
        else:
            # Fallback: model's polygon/bbox.
            _draw_region_mask(mask, region, width, height, pad)
    if mask.sum() > 0:
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)
    return mask


def detect_bright_band(image: np.ndarray, bright_thresh: int = 200,
                       min_area: int = 500) -> np.ndarray:
    """Detect a bright (white/light) watermark band deterministically.

    Many watermarks are white/light text over a darker background. This finds
    bright pixels (gray > `bright_thresh`) across the whole image, keeps only
    connected components large enough to be text (>= `min_area`), and returns a
    full-size mask. Useful when the model's bbox for a diagonal/white watermark
    is unreliable — this locates it from the pixels directly.

    Returns a full-size mask (255 at bright watermark pixels).
    """
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bright = (gray > bright_thresh).astype(np.uint8) * 255

    # Keep only sizable connected components (text, not specular noise).
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
    mask = np.zeros((height, width), dtype=np.uint8)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            mask[labels == i] = 255
    return mask


def refine_mask_by_color(image: np.ndarray, mask: np.ndarray,
                         color_tol: int = 60) -> np.ndarray:
    """Refine a coarse mask to keep only pixels matching the watermark's color.

    A polygon/bbox mask often overlaps background (skin, wall, etc.). This
    computes the dominant color inside the masked region and keeps only pixels
    within `color_tol` of it, so we erase the watermark glyphs but NOT the
    surrounding background. Falls back to the original mask if the region is too
    small to estimate a color from.
    """
    if mask.sum() == 0:
        return mask
    region_px = image[mask > 0]
    if len(region_px) < 50:
        return mask  # too few pixels to estimate color reliably

    # Dominant color = median of the masked region (robust to outliers).
    median = np.median(region_px, axis=0).astype(np.float32)

    refined = np.zeros_like(mask)
    # Only consider pixels inside the original mask.
    ys, xs = np.where(mask > 0)
    for y, x in zip(ys, xs):
        px = image[y, x].astype(np.float32)
        if np.linalg.norm(px - median) <= color_tol:
            refined[y, x] = 255

    # If refinement removed almost everything (e.g. multi-color watermark),
    # keep the original mask rather than erasing nothing.
    if refined.sum() < 0.1 * mask.sum():
        return mask
    return refined


def refine_mask_adaptive(image: np.ndarray, mask: np.ndarray,
                         color_tol: int = 60) -> np.ndarray:
    """Refine the mask using per-region adaptive foreground/background contrast.

    More robust than `refine_mask_by_color` for watermarks whose color is not
    uniform (e.g. semi-transparent text over varied background). For each region
    (connected component) in the mask, it estimates the local background color
    from a ring around the region and keeps only pixels that differ from that
    background by more than `color_tol`.
    """
    if mask.sum() == 0:
        return mask

    refined = np.zeros_like(mask)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    for i in range(1, n):  # skip background label 0
        x, y, w, h, area = stats[i]
        # Expand a ring around the component to sample background.
        x0 = max(0, x - 5)
        y0 = max(0, y - 5)
        x1 = min(mask.shape[1], x + w + 5)
        y1 = min(mask.shape[0], y + h + 5)
        ring = np.zeros_like(mask)
        ring[y0:y1, x0:x1] = 255
        ring[labels == i] = 0  # remove the component itself
        bg_px = image[ring > 0]
        if len(bg_px) < 20:
            # Not enough background to estimate — keep the component as-is.
            refined[labels == i] = 255
            continue

        bg_median = np.median(bg_px, axis=0).astype(np.float32)
        comp_ys, comp_xs = np.where(labels == i)
        for cy, cx in zip(comp_ys, comp_xs):
            px = image[cy, cx].astype(np.float32)
            if np.linalg.norm(px - bg_median) > color_tol:
                refined[cy, cx] = 255

    # Safety: if we erased almost nothing, keep the original mask.
    if refined.sum() < 0.1 * mask.sum():
        return mask
    return refined


def _inpaint_opencv(image: np.ndarray, mask: np.ndarray, radius: int) -> np.ndarray:
    """Deterministic reconstruction via OpenCV Telea inpainting."""
    return cv2.inpaint(image, mask, radius, cv2.INPAINT_TELEA)


def _inpaint_lama(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Deep reconstruction via LaMa (Fourier-convolution inpainting).

    Uses `simple_lama_inpainting` (the maintained pip package). Requires the
    optional `lama` extras — see requirements-lama.txt. Install in a Python
    3.12 venv (the package does not build on 3.13).
    """
    try:
        from simple_lama_inpainting import SimpleLama
    except ImportError as exc:
        raise RuntimeError(
            "LaMa reconstructor requires `simple-lama-inpainting`. "
            "Install with: pip install simple-lama-inpainting "
            "(in a Python 3.12 venv — it does not build on 3.13)."
        ) from exc

    # SimpleLama expects RGB image and a 0-255 (or 0/1) mask.
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mask_u8 = (mask > 0).astype(np.uint8) * 255

    model = SimpleLama()  # CPU by default
    result = model(rgb, mask_u8)
    result = np.asarray(result)
    return cv2.cvtColor(result, cv2.COLOR_RGB2BGR)


def _pick_radius(regions: list[dict], default: int) -> int:
    """Tune inpainting radius from region opacity/background hints.

    Translucent (low-opacity) watermarks need a smaller radius so we don't
    over-smooth the underlying texture; solid watermarks can use a larger one.
    """
    opacities = [r.get("opacity") for r in regions if isinstance(r.get("opacity"), (int, float))]
    if not opacities:
        return default
    avg_opacity = sum(opacities) / len(opacities)
    if avg_opacity < 0.4:
        return max(2, default - 2)
    if avg_opacity > 0.85:
        return default + 2
    return default


def inpaint(image: np.ndarray, regions: list[dict], radius: int = 5,
            reconstructor: str = "opencv", refine_color: bool = False,
            color_tol: int = 60, refine_mode: str = "adaptive",
            segment: bool = False, contrast_thresh: float = 0.15,
            fill_hollow: bool = False) -> np.ndarray:
    """Erase watermark regions and reconstruct the underlying image.

    Args:
        image: BGR image (numpy array).
        regions: List of region dicts from `locate_watermarks`.
        radius: Base inpainting radius (OpenCV reconstructor only); may be
            auto-tuned from region opacity hints.
        reconstructor: "opencv" (deterministic) or "lama" (deep).
        refine_color: If True, refine the mask to keep only watermark pixels,
            avoiding over-erasing background.
        color_tol: Color distance tolerance for refinement.
        refine_mode: "adaptive" (per-region foreground/background contrast) or
            "median" (single dominant color per region).
        segment: If True, build the mask by deterministically segmenting the
            watermark pixels from the image (robust to model color/position
            hallucinations), instead of using the model's polygon/masks.
        contrast_thresh: Contrast threshold for `segment` mode.
        fill_hollow: If True, reconnect hollow/outlined watermark strokes into
            solid glyph shapes (dilate + close) before inpainting.
    """
    height, width = image.shape[:2]
    if segment:
        mask = build_mask_deterministic(image, regions, contrast_thresh=contrast_thresh)
    else:
        mask = build_mask(width, height, regions)
    if mask.sum() == 0:
        return image.copy()

    if fill_hollow:
        mask = fill_hollow_strokes(mask)

    if refine_color:
        if refine_mode == "median":
            mask = refine_mask_by_color(image, mask, color_tol=color_tol)
        else:
            mask = refine_mask_adaptive(image, mask, color_tol=color_tol)
        if mask.sum() == 0:
            return image.copy()

    if reconstructor == "lama":
        return _inpaint_lama(image, mask)

    effective_radius = _pick_radius(regions, radius)
    return _inpaint_opencv(image, mask, effective_radius)


def save_artifacts(image: np.ndarray, regions: list[dict], artifacts_dir: str,
                   refine_color: bool = False, color_tol: int = 60,
                   refine_mode: str = "adaptive"):
    """Write auxiliary artifacts: mask image + per-region crops."""
    os.makedirs(artifacts_dir, exist_ok=True)
    height, width = image.shape[:2]
    mask = build_mask(width, height, regions)
    cv2.imwrite(os.path.join(artifacts_dir, "mask.png"), mask)

    if refine_color:
        if refine_mode == "median":
            refined = refine_mask_by_color(image, mask, color_tol=color_tol)
        else:
            refined = refine_mask_adaptive(image, mask, color_tol=color_tol)
        cv2.imwrite(os.path.join(artifacts_dir, "mask_refined.png"), refined)

    for i, region in enumerate(regions):
        bbox = region.get("bbox", [0, 0, 0, 0])
        x, y, w, h = _denorm(bbox, width, height)
        pad = 16
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(width, x + w + pad)
        y1 = min(height, y + h + pad)
        crop = image[y0:y1, x0:x1]
        cv2.imwrite(os.path.join(artifacts_dir, f"region_{i}.png"), crop)
