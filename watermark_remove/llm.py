"""DeepSeek Vision client for watermark detection.

The DeepSeek multimodal model (`deepseek-v4-flash-vision-exp`) is used for
**detection and localization** only — it analyzes the image and returns JSON
bounding boxes for watermark regions, plus a semantic label and confidence for
each.

The model is understanding-only: it accepts image input and returns text/JSON,
but cannot generate or edit images. Pixel reconstruction is therefore handled
separately in `remove.py` (deterministic inpainting + optional deep inpainting).
"""
import base64
import json
import re

from openai import OpenAI


def _client(api_key, base_url):
    return OpenAI(api_key=api_key, base_url=base_url)


def _encode_image_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def locate_watermarks_consensus(image_bytes: bytes,
                                target_watermarks: list[str] | None,
                                api_key: str, base_url: str, model: str,
                                runs: int = 3) -> list[dict]:
    """Run localization multiple times and merge into a stable consensus.

    The vision model is non-deterministic even at temperature=0, so a single
    call can miss or misplace a watermark. This runs `runs` times and unions the
    results, keeping the highest-confidence copy of each region (matched by bbox
    overlap). Returns the same region schema as `locate_watermarks`.
    """
    all_regions = []
    for _ in range(runs):
        regions = locate_watermarks(image_bytes, target_watermarks,
                                    api_key, base_url, model)
        all_regions.extend(regions)

    if not all_regions:
        return []

    # Cluster regions by bbox IoU and keep the best (highest confidence) per cluster.
    merged = []
    for region in all_regions:
        bbox = region.get("bbox")
        placed = False
        for m in merged:
            if _iou(bbox, m.get("bbox")) > 0.4:
                # Same cluster: keep the higher-confidence one, merge masks.
                if (region.get("confidence") or 0) > (m.get("confidence") or 0):
                    m.update(region)
                placed = True
                break
        if not placed:
            merged.append(dict(region))

    # Sort by confidence descending for stable output.
    merged.sort(key=lambda r: r.get("confidence") or 0, reverse=True)
    return merged


def _iou(a, b):
    """Intersection-over-Union of two [x, y, w, h] boxes (normalized)."""
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0.0
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def locate_watermarks(image_bytes: bytes,
                      target_watermarks: list[str] | None,
                      api_key: str, base_url: str, model: str) -> list[dict]:
    """Ask the vision model to locate watermark regions.

    Args:
        image_bytes: Raw image bytes.
        target_watermarks: Optional list of watermark descriptions. When
            provided, the model is instructed to locate ONLY regions matching
            one of these descriptions and ignore everything else. When None or
            empty, all detected watermarks/overlays are returned.

    Returns a list of regions, each:
        {
            "label": str,
            "confidence": float,
            "bbox": [x, y, w, h],      # normalized 0-1, tight box
            "polygon": [[x, y], ...],  # normalized 0-1, outline of watermark
            "background": str,         # what's behind the watermark
            "opacity": float,          # 0-1 solidity estimate
        }
    The polygon (when present) is the preferred mask source; the bbox is a
    fallback. All coordinates are normalized relative to image width/height.
    """
    client = _client(api_key, base_url)
    b64 = _encode_image_bytes(image_bytes)

    system = (
        "You are a precise image analysis expert. Locate watermarks, logos, "
        "timestamps, or overlay text in the image. Output ONLY valid JSON."
    )

    if target_watermarks:
        targets = "; ".join(f'"{w}"' for w in target_watermarks)
        scope = (
            f"You are given the following target watermark description(s): {targets}.\n"
            "Locate ONLY the regions that match one of these descriptions. "
            "IGNORE all other watermarks, logos, text, or overlays that do NOT "
            "match — do not report them. If none of the described watermarks are "
            "present, return an empty regions array.\n"
        )
    else:
        scope = (
            "Locate EVERY watermark, logo, timestamp, or overlay text in the "
            "image. Report all of them.\n"
        )

    user = (
        "Analyze the attached image.\n"
        + scope +
        "Your output will be used to build a pixel mask for an inpainting model, "
        "so precision matters more than speed. For EACH watermark return:\n"
        '  "label": a short description (e.g. "bottom-right logo"),\n'
        '  "confidence": 0.0-1.0,\n'
        '  "bbox": [x, y, width, height] — a TIGHT bounding box (normalized 0-1) '
        "that just encloses the watermark,\n"
        '  "masks": an array of polygons. EACH polygon is a tight [x, y] point '
        "list tracing ONE glyph, letter, or small cluster of the watermark "
        "(normalized 0-1). For a text watermark, return one small polygon per "
        "word or character, tightly hugging the visible pixels. Do NOT return a "
        "single rectangle or fat band around the whole watermark — that would "
        "erase background. Use 8-20 points per mask.\n"
        '  "background": a short description of what lies BEHIND the watermark '
        '(e.g. "sky", "white wall", "grass", "skin") — this guides reconstruction.\n'
        '  "opacity": 0.0-1.0 estimate of how opaque/solid the watermark is.\n'
        "Return a JSON object with a single key \"regions\", an array of these "
        "objects.\n"
        "If no matching watermark is present, return {{\"regions\": []}}."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()
    data = _parse_json(raw)
    regions = data.get("regions", []) if isinstance(data, dict) else []
    valid = []
    for r in regions:
        if not isinstance(r, dict):
            continue
        # A region is usable if it has a bbox or a polygon.
        if "bbox" not in r and "polygon" not in r:
            continue
        valid.append(r)
    return valid


def refine_region(image_bytes: bytes, bbox: list, api_key: str, base_url: str,
                  model: str, pad_ratio: float = 0.15) -> dict | None:
    """Tighten a region's bbox by re-localizing within a cropped view.

    The initial localization often gives a loose bbox (especially for diagonal
    watermarks). Cropping the region (with padding) removes the confusing
    surrounding context and lets the model give a much tighter box.

    Args:
        image_bytes: Raw bytes of the FULL image.
        bbox: [x, y, w, h] normalized (0-1) in full-image coordinates.
        pad_ratio: Fraction of the bbox size to pad on each side when cropping.

    Returns the refined region dict (bbox/masks in full-image coordinates), or
    None if the model found nothing in the crop.
    """
    import cv2
    import numpy as np

    # Decode the full image to crop it.
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    H, W = img.shape[:2]

    x, y, w, h = bbox
    # Pad the crop so the watermark isn't clipped.
    px = w * pad_ratio
    py = h * pad_ratio
    cx0 = max(0, int((x - px) * W))
    cy0 = max(0, int((y - py) * H))
    cx1 = min(W, int((x + w + px) * W))
    cy1 = min(H, int((y + h + py) * H))
    if cx1 - cx0 < 8 or cy1 - cy0 < 8:
        return None

    crop = img[cy0:cy1, cx0:cx1]
    ok, buf = cv2.imencode(".png", crop)
    if not ok:
        return None
    crop_b64 = base64.b64encode(buf.tobytes()).decode("ascii")

    client = _client(api_key, base_url)
    user = (
        "This is a CROPPED region of a larger image. Locate the watermark(s) "
        "within this crop and return a TIGHT bounding box for each.\n"
        "Return a JSON object with a single key \"regions\", an array of:\n"
        '  {{"label": "<description>", "confidence": <0-1>, '
        '"bbox": [x, y, width, height]}}\n'
        "bbox uses NORMALIZED coordinates (0-1) relative to THIS CROP's width "
        "and height, with x/y as the top-left corner.\n"
        "Trace tightly — the box should just enclose the watermark glyphs, not "
        "the surrounding background. If no watermark is visible in this crop, "
        "return {{\"regions\": []}}."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a precise image analysis expert. Output ONLY valid JSON."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{crop_b64}"}},
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()
    data = _parse_json(raw)
    regions = data.get("regions", []) if isinstance(data, dict) else []
    if not regions:
        return None

    # Take the highest-confidence region and map its bbox back to full-image coords.
    best = max(regions, key=lambda r: r.get("confidence", 0) or 0)
    rb = best.get("bbox")
    if not rb or len(rb) != 4:
        return None

    rx, ry, rw, rh = rb
    full_x = cx0 / W + rx * (cx1 - cx0) / W
    full_y = cy0 / H + ry * (cy1 - cy0) / H
    full_w = rw * (cx1 - cx0) / W
    full_h = rh * (cy1 - cy0) / H

    refined = dict(best)
    refined["bbox"] = [full_x, full_y, full_w, full_h]

    # Sanity check: the refined bbox must overlap the original bbox (the model
    # should tighten, not jump to a completely different region). Reject if the
    # refined box's center lands far outside the original box.
    ox, oy, ow, oh = bbox
    ocx, ocy = ox + ow / 2, oy + oh / 2
    rcx, rcy = full_x + full_w / 2, full_y + full_h / 2
    if abs(rcx - ocx) > ow or abs(rcy - ocy) > oh:
        return None  # refined box jumped elsewhere — discard

    return refined


def verify_removal(image_bytes: bytes,
                   api_key: str, base_url: str, model: str) -> dict:
    """Ask the vision model whether any watermark residue remains after removal.

    Returns a dict:
        {"clean": bool, "remaining": [{"label": str, "bbox": [...]}]}
    where `remaining` lists any watermark regions still visible (normalized
    coords). Used to drive an iterative refine loop.
    """
    client = _client(api_key, base_url)
    b64 = _encode_image_bytes(image_bytes)

    user = (
        "Analyze the attached image. It has been processed to remove watermarks, "
        "but some residue may remain.\n"
        "Return a JSON object with:\n"
        '  "clean": true if NO watermark/logo/text-overlay remains, else false,\n'
        '  "remaining": an array of leftover regions, each '
        '{{"label": "<description>", "confidence": <0.0-1.0>, '
        '"bbox": [x, y, width, height]}} with NORMALIZED coordinates (0-1).\n'
        "Only report regions you are genuinely confident are leftover watermark "
        "residue — do NOT report natural image content, shadows, or textures.\n"
        "If the image is fully clean, return {{\"clean\": true, \"remaining\": []}}."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a precise image quality inspector. Output ONLY valid JSON."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()
    data = _parse_json(raw)
    if not isinstance(data, dict):
        return {"clean": True, "remaining": []}
    return {
        "clean": bool(data.get("clean", True)),
        "remaining": data.get("remaining", []),
    }


def evaluate_quality(input_bytes: bytes, output_bytes: bytes,
                     api_key: str, base_url: str, model: str) -> dict:
    """Ask the vision model to compare input vs output and critique the removal.

    Passes BOTH the original and the cleaned image so the model can judge how
    well the watermark was removed and whether the reconstruction damaged the
    underlying content.

    Returns a dict:
        {
          "score": float 0-10,          # overall quality
          "watermark_removed": bool,    # is the watermark fully gone?
          "content_damaged": bool,      # was non-watermark content altered?
          "residue": str,               # description of any leftover watermark
          "artifacts": str,             # description of smearing/blurring/etc.
          "notes": str,                 # free-form critique
        }
    """
    client = _client(api_key, base_url)
    b64_in = _encode_image_bytes(input_bytes)
    b64_out = _encode_image_bytes(output_bytes)

    user = (
        "You will be shown two images: the ORIGINAL image (with a watermark) and "
        "the CLEANED image (after watermark removal).\n"
        "Compare them and evaluate the QUALITY of the watermark removal.\n"
        "Return a JSON object with:\n"
        '  "score": 0-10 overall quality (10 = perfect, invisible removal, no damage),\n'
        '  "watermark_removed": true if the watermark is FULLY gone, else false,\n'
        '  "content_damaged": true if any NON-watermark content was altered, '
        "smeared, blurred, or erased, else false,\n"
        '  "residue": a short description of any leftover watermark (or "" if none),\n'
        '  "artifacts": a short description of any smearing/blurring/distortion '
        'introduced by the removal (or "" if none),\n'
        '  "notes": a one-sentence critique of what could be improved.\n'
        "Be specific and honest — your feedback drives the next iteration."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a precise image quality evaluator. Output ONLY valid JSON."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_in}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_out}"}},
                ],
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()
    data = _parse_json(raw)
    if not isinstance(data, dict):
        return {"score": None, "watermark_removed": None, "content_damaged": None,
                "residue": "", "artifacts": "", "notes": ""}
    return {
        "score": data.get("score"),
        "watermark_removed": data.get("watermark_removed"),
        "content_damaged": data.get("content_damaged"),
        "residue": data.get("residue", ""),
        "artifacts": data.get("artifacts", ""),
        "notes": data.get("notes", ""),
    }


def _parse_json(raw: str) -> dict | list:
    """Rescue-parse JSON, stripping markdown fences if present."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to first balanced JSON object/array.
        start = cleaned.find("{")
        if start == -1:
            start = cleaned.find("[")
        if start != -1:
            try:
                decoder = json.JSONDecoder()
                return decoder.raw_decode(cleaned[start:])[0]
            except json.JSONDecodeError:
                pass
        return {}
