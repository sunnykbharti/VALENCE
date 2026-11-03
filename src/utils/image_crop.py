"""Image cropping and region overlay utilities for Point, Inspect, Ask.

Ensures deterministic IDs, input validation, and clear labelling of user-selected
regions (never mislabeled as AI-detected components).
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Union

from PIL import Image, ImageDraw


def crop_image_region(
    image_path: Union[str, Path],
    box_pct: tuple[float, float, float, float],
    output_dir: Optional[Path] = None,
) -> tuple[Path, str, tuple[int, int, int, int]]:
    """Crops an image region based on user-selected percentage coordinates.

    Args:
        image_path: Path to the original source image.
        box_pct: Tuple of (x_min_pct, y_min_pct, x_max_pct, y_max_pct) in range 0.0 - 100.0.
        output_dir: Optional directory to store cropped image. Defaults to system temp.

    Returns:
        (cropped_image_path, crop_id, (px1, py1, px2, py2))

    Raises:
        FileNotFoundError: If image does not exist.
        ValueError: If box percentages are invalid, out-of-bounds, or crop area is degenerate.
    """
    p = Path(image_path)
    if not p.is_file():
        raise FileNotFoundError(f"Source image not found at '{p}'")

    x_min, y_min, x_max, y_max = box_pct

    # Validate bounds
    if not (0.0 <= x_min < x_max <= 100.0):
        raise ValueError(f"Invalid horizontal percentage range: [{x_min}, {x_max}]. Must satisfy 0 <= x_min < x_max <= 100.")
    if not (0.0 <= y_min < y_max <= 100.0):
        raise ValueError(f"Invalid vertical percentage range: [{y_min}, {y_max}]. Must satisfy 0 <= y_min < y_max <= 100.")

    with Image.open(p) as img:
        img_rgb = img.convert("RGB")
        w, h = img_rgb.size

        px1 = max(0, min(w - 1, int(round((x_min / 100.0) * w))))
        py1 = max(0, min(h - 1, int(round((y_min / 100.0) * h))))
        px2 = max(px1 + 1, min(w, int(round((x_max / 100.0) * w))))
        py2 = max(py1 + 1, min(h, int(round((y_max / 100.0) * h))))

        crop_w = px2 - px1
        crop_h = py2 - py1
        if crop_w < 10 or crop_h < 10 or (crop_w * crop_h) < 100:
            raise ValueError(f"Selected crop region is too small ({crop_w}x{crop_h} px). Must be at least 10x10 and 100 px^2.")

        cropped = img_rgb.crop((px1, py1, px2, py2))

        # Generate deterministic crop ID from bytes
        crop_bytes = cropped.tobytes()
        crop_hash = hashlib.sha256(crop_bytes).hexdigest()[:12]
        crop_id = f"img_crop_{crop_hash}"

        # Save to output path
        if output_dir:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            crop_path = out_dir / f"{crop_id}.png"
        else:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix=f"{crop_id}_")
            crop_path = Path(tmp.name)
            tmp.close()

        cropped.save(crop_path, format="PNG")

    return crop_path, crop_id, (px1, py1, px2, py2)


def draw_user_region_overlay(
    image_path: Union[str, Path],
    box_pct: tuple[float, float, float, float],
) -> Image.Image:
    """Draws a highlighted bounding box labeled 'User-selected region' over the original image.

    Args:
        image_path: Path to original source image.
        box_pct: (x_min, y_min, x_max, y_max) percentages.

    Returns:
        PIL Image with visual annotation.
    """
    p = Path(image_path)
    if not p.is_file():
        raise FileNotFoundError(f"Source image not found at '{p}'")

    x_min, y_min, x_max, y_max = box_pct
    with Image.open(p) as img:
        annotated = img.convert("RGB").copy()
        w, h = annotated.size

        px1 = max(0, min(w - 1, int(round((x_min / 100.0) * w))))
        py1 = max(0, min(h - 1, int(round((y_min / 100.0) * h))))
        px2 = max(px1 + 1, min(w, int(round((x_max / 100.0) * w))))
        py2 = max(py1 + 1, min(h, int(round((y_max / 100.0) * h))))

        draw = ImageDraw.Draw(annotated)
        # Cyan bounding box
        draw.rectangle([px1, py1, px2, py2], outline=(0, 220, 255), width=3)

        # Label: STRICTLY 'User-selected region'
        label_text = "User-selected region"
        label_h = 20
        label_w = 160
        label_y1 = max(0, py1 - label_h - 2)
        label_y2 = label_y1 + label_h
        draw.rectangle([px1, label_y1, px1 + label_w, label_y2], fill=(0, 100, 150))
        draw.text((px1 + 5, label_y1 + 3), label_text, fill=(255, 255, 255))

    return annotated

