"""Isolated capability spike script for Qwen2.5-VL localization on Ollama.

Runs outside the production application codebase.
Tests visual component localization on 4 diagnostic test cases.
Measures wall-clock latency, memory usage, coordinate conventions, and failures.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VLM_MODEL = os.getenv("OLLAMA_VLM_MODEL", "qwen2.5vl:7b")


def get_available_memory_mb() -> float:
    """Estimates available system memory in MB from vm_stat."""
    try:
        out = subprocess.check_output(["vm_stat"], text=True)
        lines = out.splitlines()
        free_pages = 0
        inactive_pages = 0
        speculative_pages = 0
        for line in lines:
            if "Pages free:" in line:
                free_pages = int(re.search(r"\d+", line).group(0))
            elif "Pages inactive:" in line:
                inactive_pages = int(re.search(r"\d+", line).group(0))
            elif "Pages speculative:" in line:
                speculative_pages = int(re.search(r"\d+", line).group(0))
        avail_bytes = (free_pages + inactive_pages + speculative_pages) * 16384
        return avail_bytes / (1024 * 1024)
    except Exception:
        return 0.0


def encode_image(image_path: Path) -> tuple[str, int, int]:
    with Image.open(image_path) as img:
        width, height = img.size
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, width, height


def query_vlm_localization(
    image_path: Path,
    target_component: str,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, float]:
    b64_image, width, height = encode_image(image_path)

    endpoint = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": VLM_MODEL,
        "prompt": user_prompt,
        "system": system_prompt,
        "images": [b64_image],
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.0,
        },
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = Request(endpoint, data=req_data, headers={"Content-Type": "application/json"})

    t0 = time.perf_counter()
    with urlopen(req, timeout=180.0) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        elapsed = time.perf_counter() - t0
        raw_text = str(res.get("response", "")).strip()
        return raw_text, elapsed


def parse_and_validate_coordinates(
    raw_response: str,
    img_width: int,
    img_height: int,
) -> dict[str, Any]:
    """Extracts JSON and strictly validates coordinates and bounds.

    Returns dict with keys:
    - status: 'candidate_found' | 'needs_better_view' | 'not_found' | 'parse_error'
    - bounding_box_norm: (x1, y1, x2, y2) in [0.0, 1.0] if candidate_found
    - bounding_box_pixels: (px1, py1, px2, py2) if candidate_found
    - coordinate_system: detected coordinate system description
    - observation: short observation summary
    - reason: uncertainty reason or failure message
    - raw_json: extracted json dict or None
    """
    # Attempt to locate JSON block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_obj_match = re.search(r"(\{.*\})", raw_response, re.DOTALL)
        json_str = json_obj_match.group(1) if json_obj_match else None

    if not json_str:
        return {
            "status": "parse_error",
            "reason": "No valid JSON structure found in response",
            "raw_json": None,
            "bounding_box_norm": None,
            "bounding_box_pixels": None,
            "coordinate_system": "unknown",
            "observation": raw_response[:200],
        }

    try:
        data = json.loads(json_str)
    except Exception as e:
        return {
            "status": "parse_error",
            "reason": f"JSON parsing failed: {e}",
            "raw_json": None,
            "bounding_box_norm": None,
            "bounding_box_pixels": None,
            "coordinate_system": "unknown",
            "observation": raw_response[:200],
        }

    found = data.get("found", False)
    if not found or data.get("status") in ("not_found", "needs_better_view", "absent"):
        return {
            "status": data.get("status", "needs_better_view" if data.get("requested_view") else "not_found"),
            "reason": data.get("reason", "Target component not clearly identified"),
            "requested_view": data.get("requested_view"),
            "raw_json": data,
            "bounding_box_norm": None,
            "bounding_box_pixels": None,
            "coordinate_system": "n/a",
            "observation": data.get("observation", data.get("description", "")),
        }

    raw_box = data.get("box_2d") or data.get("bounding_box") or data.get("bbox")
    if not raw_box or not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
        return {
            "status": "parse_error",
            "reason": f"Target declared found but box_2d missing or invalid: {raw_box}",
            "raw_json": data,
            "bounding_box_norm": None,
            "bounding_box_pixels": None,
            "coordinate_system": "unknown",
            "observation": data.get("observation", ""),
        }

    # Verify numeric and finite
    try:
        coords = [float(v) for v in raw_box]
        for c in coords:
            if not isinstance(c, (int, float)) or c != c or abs(c) == float("inf"):
                raise ValueError(f"Non-finite coordinate value: {c}")
    except Exception as e:
        return {
            "status": "parse_error",
            "reason": f"Coordinate non-numeric or non-finite: {e}",
            "raw_json": data,
            "bounding_box_norm": None,
            "bounding_box_pixels": None,
            "coordinate_system": "invalid",
            "observation": data.get("observation", ""),
        }

    c0, c1, c2, c3 = coords

    # Parse coordinates as [x1, y1, x2, y2] normalized to 0-1000 scale
    x1_val, y1_val, x2_val, y2_val = c0, c1, c2, c3

    # Check scale
    if max(coords) > 1.0 and max(coords) <= 1000.0:
        coord_sys = "normalized_0_1000 (x1, y1, x2, y2)"
        norm_x1 = x1_val / 1000.0
        norm_y1 = y1_val / 1000.0
        norm_x2 = x2_val / 1000.0
        norm_y2 = y2_val / 1000.0
    elif max(coords) <= 1.0:
        coord_sys = "normalized_0_1 (x1, y1, x2, y2)"
        norm_x1 = x1_val
        norm_y1 = y1_val
        norm_x2 = x2_val
        norm_y2 = y2_val
    else:
        coord_sys = "pixel_coordinates (x1, y1, x2, y2)"
        norm_x1 = x1_val / img_width
        norm_y1 = y1_val / img_height
        norm_x2 = x2_val / img_width
        norm_y2 = y2_val / img_height

    # Strict bounds and ordering validation (do NOT clamp)
    if not (0.0 <= norm_x1 <= 1.0 and 0.0 <= norm_y1 <= 1.0 and 0.0 <= norm_x2 <= 1.0 and 0.0 <= norm_y2 <= 1.0):
        return {
            "status": "parse_error",
            "reason": f"Coordinates out of normalized bounds [0.0, 1.0]: ({norm_x1:.4f}, {norm_y1:.4f}, {norm_x2:.4f}, {norm_y2:.4f})",
            "raw_json": data,
            "bounding_box_norm": None,
            "bounding_box_pixels": None,
            "coordinate_system": coord_sys,
            "observation": data.get("observation", ""),
        }

    if norm_x1 >= norm_x2 or norm_y1 >= norm_y2:
        return {
            "status": "parse_error",
            "reason": f"Invalid box ordering: x1 ({norm_x1:.4f}) >= x2 ({norm_x2:.4f}) or y1 ({norm_y1:.4f}) >= y2 ({norm_y2:.4f})",
            "raw_json": data,
            "bounding_box_norm": None,
            "bounding_box_pixels": None,
            "coordinate_system": coord_sys,
            "observation": data.get("observation", ""),
        }

    px1 = int(round(norm_x1 * img_width))
    py1 = int(round(norm_y1 * img_height))
    px2 = int(round(norm_x2 * img_width))
    py2 = int(round(norm_y2 * img_height))

    return {
        "status": "candidate_found",
        "reason": None,
        "requested_view": None,
        "raw_json": data,
        "bounding_box_norm": (norm_x1, norm_y1, norm_x2, norm_y2),
        "bounding_box_pixels": (px1, py1, px2, py2),
        "coordinate_system": coord_sys,
        "observation": data.get("observation", data.get("description", f"Located candidate for {data.get('label')}")),
    }


def draw_overlay(
    image_path: Path,
    box_pixels: tuple[int, int, int, int],
    label: str,
    output_path: Path,
) -> None:
    with Image.open(image_path) as img:
        img_copy = img.convert("RGB")
        draw = ImageDraw.Draw(img_copy)
        px1, py1, px2, py2 = box_pixels

        # Draw candidate box in vibrant cyan/amber with high visibility
        outline_color = (0, 230, 255)
        for offset in range(3):  # 3-pixel border
            draw.rectangle([px1 - offset, py1 - offset, px2 + offset, py2 + offset], outline=outline_color)

        # Label background pill
        text_str = f" Candidate: {label} "
        draw.rectangle([px1, max(0, py1 - 20), px1 + len(text_str) * 8, py1], fill=outline_color)
        draw.text((px1 + 2, max(0, py1 - 18)), text_str, fill=(0, 0, 0))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img_copy.save(output_path)


def run_all_spike_tests() -> dict[str, Any]:
    test_cases = [
        {
            "id": "case_1_visible",
            "name": "Case 1: Clearly Visible Target",
            "image_path": Path("tests/fixtures/synthetic_plc_leds_normal.png"),
            "target": "LED status indicators",
            "prompt": (
                "Locate the 'LED status indicators' on the front panel of the Siemens S7-1200 PLC in this image.\n"
                "Return your output strictly as a JSON object in this format:\n"
                "If visible and localized:\n"
                "{\n"
                '  "found": true,\n'
                '  "status": "candidate_found",\n'
                '  "label": "LED status indicators",\n'
                '  "box_2d": [x1, y1, x2, y2],\n'
                '  "format": "[x1, y1, x2, y2] in 0-1000 scale where x1 < x2 and y1 < y2",\n'
                '  "observation": "Brief factual visual description"\n'
                "}\n"
                "If not clearly visible, obscured, or absent:\n"
                "{\n"
                '  "found": false,\n'
                '  "status": "needs_better_view",\n'
                '  "reason": "Specific reason why target cannot be localized",\n'
                '  "requested_view": "Description of closer angle or view needed"\n'
                "}"
            ),
        },
        {
            "id": "case_2_angled",
            "name": "Case 2: Same Target from Another Angle / Module View",
            "image_path": Path("tests/fixtures/synthetic_ambiguous_model.png"),
            "target": "LED status indicators",
            "prompt": (
                "Locate the 'LED status indicators' on the Siemens S7-1200 PLC module in this photo.\n"
                "Return your output strictly as a JSON object in this format:\n"
                "If visible and localized:\n"
                "{\n"
                '  "found": true,\n'
                '  "status": "candidate_found",\n'
                '  "label": "LED status indicators",\n'
                '  "box_2d": [x1, y1, x2, y2],\n'
                '  "format": "[x1, y1, x2, y2] in 0-1000 scale where x1 < x2 and y1 < y2",\n'
                '  "observation": "Brief factual visual description"\n'
                "}\n"
                "If not clearly visible, obscured, or absent:\n"
                "{\n"
                '  "found": false,\n'
                '  "status": "needs_better_view",\n'
                '  "reason": "Specific reason why target cannot be localized",\n'
                '  "requested_view": "Description of closer angle or view needed"\n'
                "}"
            ),
        },
        {
            "id": "case_3_absent",
            "name": "Case 3: Target Absent",
            "image_path": Path("tests/fixtures/synthetic_unknown_equipment.png"),
            "target": "Siemens S7-1200 RUN/STOP LED",
            "prompt": (
                "Locate the 'Siemens S7-1200 RUN/STOP LED' in this equipment photo.\n"
                "If the target is NOT present on this machine, you MUST report found: false.\n"
                "Return your output strictly as a JSON object in this format:\n"
                "{\n"
                '  "found": false,\n'
                '  "status": "not_found",\n'
                '  "reason": "Target component is not present on this equipment",\n'
                '  "requested_view": "Photograph of Siemens S7-1200 PLC required"\n'
                "}\n"
                "Only if the Siemens S7-1200 RUN/STOP LED is genuinely visible:\n"
                "{\n"
                '  "found": true,\n'
                '  "status": "candidate_found",\n'
                '  "label": "Siemens S7-1200 RUN/STOP LED",\n'
                '  "box_2d": [x1, y1, x2, y2],\n'
                '  "format": "[x1, y1, x2, y2] in 0-1000 scale",\n'
                '  "observation": "Description"\n'
                "}"
            ),
        },
        {
            "id": "case_4_blurry",
            "name": "Case 4: Target Obscured / Blurry",
            "image_path": Path("tests/fixtures/synthetic_blurry_panel.png"),
            "target": "PLC RUN/STOP diagnostic LED",
            "prompt": (
                "Locate the 'PLC RUN/STOP diagnostic LED' in this inspection photograph.\n"
                "If the image resolution, blur, lighting, or focus is inadequate to identify the exact LED, report found: false.\n"
                "Return your output strictly as a JSON object in this format:\n"
                "If blur/resolution prevents reliable localization:\n"
                "{\n"
                '  "found": false,\n'
                '  "status": "needs_better_view",\n'
                '  "reason": "Image quality, blur, or glare prevents localization",\n'
                '  "requested_view": "Close-up in-focus photo with adequate lighting"\n'
                "}\n"
                "If unmistakably localized:\n"
                "{\n"
                '  "found": true,\n'
                '  "status": "candidate_found",\n'
                '  "label": "PLC RUN/STOP diagnostic LED",\n'
                '  "box_2d": [x1, y1, x2, y2],\n'
                '  "format": "[x1, y1, x2, y2] in 0-1000 scale",\n'
                '  "observation": "Description"\n'
                "}"
            ),
        },
    ]

    results = []
    out_dir = Path("scripts/spike_output")
    out_dir.mkdir(parents=True, exist_ok=True)

    system_prompt = (
        "You are an air-gapped industrial visual inspection localization engine. "
        "Locate industrial components precisely. If a target is absent, obscured, or blurry, "
        "faithfully report it as not found or needing a better view. Never hallucinate coordinates."
    )

    print(f"=== STARTING ISOLATED REAL-MODEL CAPABILITY SPIKE ===")
    print(f"Model: {VLM_MODEL}")
    print(f"Endpoint: {OLLAMA_BASE_URL}\n")

    for tc in test_cases:
        print(f"--- Running {tc['name']} ({tc['id']}) ---")
        img_p = tc["image_path"]
        if not img_p.exists():
            print(f"ERROR: Image not found: {img_p}")
            continue

        with Image.open(img_p) as img:
            w, h = img.size

        mem_before = get_available_memory_mb()
        print(f"Image dimensions: {w}x{h} px | Available RAM before: {mem_before:.0f} MB")

        try:
            raw_resp, duration = query_vlm_localization(
                image_path=img_p,
                target_component=tc["target"],
                system_prompt=system_prompt,
                user_prompt=tc["prompt"],
            )
            mem_after = get_available_memory_mb()

            parsed = parse_and_validate_coordinates(raw_resp, w, h)
            overlay_file = None
            if parsed["status"] == "candidate_found" and parsed["bounding_box_pixels"]:
                overlay_file = out_dir / f"{tc['id']}_overlay.png"
                draw_overlay(img_p, parsed["bounding_box_pixels"], tc["target"], overlay_file)
                print(f"Overlay generated: {overlay_file}")

            res_entry = {
                "test_id": tc["id"],
                "test_name": tc["name"],
                "target": tc["target"],
                "image_path": str(img_p),
                "image_dimensions": f"{w}x{h}",
                "exact_prompt": tc["prompt"],
                "raw_response": raw_resp,
                "parsed_result": parsed,
                "overlay_path": str(overlay_file) if overlay_file else None,
                "duration_seconds": round(duration, 2),
                "memory_before_mb": round(mem_before, 1),
                "memory_after_mb": round(mem_after, 1),
            }
            results.append(res_entry)

            print(f"Duration: {duration:.2f}s | Status: {parsed['status']}")
            print(f"Raw Output: {raw_resp[:160]}...")
            if parsed["status"] == "candidate_found":
                print(f"Normalized Box: {parsed['bounding_box_norm']}")
                print(f"Pixel Box: {parsed['bounding_box_pixels']}")
            else:
                print(f"Reason: {parsed['reason']} | Requested: {parsed.get('requested_view')}")
            print()

        except Exception as e:
            print(f"ERROR during {tc['id']}: {e}\n")
            results.append({
                "test_id": tc["id"],
                "test_name": tc["name"],
                "error": str(e),
            })

    # Save detailed JSON report
    report_path = out_dir / "spike_results.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Spike report saved to: {report_path}")
    return {"results": results, "report_path": str(report_path)}


if __name__ == "__main__":
    run_all_spike_tests()

