"""Local vision processing module for VALENCE (Member B).

Interprets industrial inspection images (labels, gauges, indicators) using a local VLM.
Preserves air-gapped constraints and ensures visual observations remain separate
from retrieved technical instructions.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import is_loopback_url

logger = logging.getLogger("valence.vision")

VISION_SYSTEM_PROMPT = (
    "You are an air-gapped industrial visual inspection assistant. "
    "Analyze the provided equipment photograph or diagram:\n"
    "1. Identify visible nameplates, model numbers, and serial tags.\n"
    "2. Transcribe visible gauge values, digital displays, and warning indicators.\n"
    "3. Note physical defects, discoloration, or wear.\n"
    "4. Explicitly state any uncertainties due to blur, glare, lighting, or partial obstruction.\n"
    "Do NOT assume an unverified model number. If a label is partially illegible, state that it is ambiguous."
)


@dataclass
class VisualInterpretation:
    """Structured result of local visual analysis.

    Attributes:
        observations: List of tentative visual observations.
        detected_equipment: Inferred equipment model identifier, if unambiguous.
        is_ambiguous: True if equipment model or readings are ambiguous/obscured.
        raw_description: Full response from the local vision model.
        vision_available: True if local vision model processed the image; False if fallback.
    """
    observations: list[str] = field(default_factory=list)
    detected_equipment: Optional[str] = None
    is_ambiguous: bool = False
    raw_description: str = ""
    vision_available: bool = True


def _read_and_encode_image(image_path: Path) -> tuple[str, str]:
    """Reads local image file and returns (base64_str, mime_type).

    Raises:
        FileNotFoundError: If image does not exist.
        ValueError: If file is empty or not an image.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Inspection image not found at '{image_path}'")

    size = image_path.stat().st_size
    if size == 0:
        raise ValueError(f"Image at '{image_path}' is empty (0 bytes).")

    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type or not mime_type.startswith("image/"):
        # Fallback inspection for common image extensions
        ext = image_path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            mime_type = "image/jpeg"
        elif ext == ".png":
            mime_type = "image/png"
        elif ext == ".webp":
            mime_type = "image/webp"
        else:
            raise ValueError(f"File '{image_path.name}' is not a recognized image format.")

    raw_bytes = image_path.read_bytes()
    b64_str = base64.b64encode(raw_bytes).decode("utf-8")
    return b64_str, mime_type


def _extract_model_candidate(text: str) -> tuple[Optional[str], bool]:
    """Extracts candidate equipment model and assesses ambiguity from text."""
    lower = text.lower()
    is_ambiguous = (
        "unclear" in lower
        or "ambiguous" in lower
        or "illegible" in lower
        or "obscured" in lower
        or "partially visible" in lower
        or "uncertain" in lower
    )

    # Search for patterns like Model: X, Model-X, Type: X
    model_patterns = [
        r"(?:model|type|equipment|unit)[\s:\-#]+([A-Za-z0-9_\-]+)",
        r"\b([A-Z][A-Za-z0-9]+-[A-Z0-9]+)\b",
    ]
    for pattern in model_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # If word is not generic
            if candidate.lower() not in ("number", "name", "tag", "plate", "id"):
                return candidate, is_ambiguous

    return None, is_ambiguous


class LocalVisionEngine:
    """Interprets local equipment inspection images using local Ollama VLM."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2-vision:11b",
        vision_fn: Optional[Callable[[Path, str], VisualInterpretation]] = None,
    ) -> None:
        if not is_loopback_url(base_url):
            raise ValueError(f"Air-gapped constraint violation: base_url must be loopback. Got '{base_url}'")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._custom_vision_fn = vision_fn

    def check_availability(self) -> tuple[bool, str]:
        """Checks if the local vision model is available in local Ollama.

        Returns (is_available, message).
        """
        if self._custom_vision_fn is not None:
            return True, "Mock vision function registered."

        endpoint = f"{self.base_url}/api/tags"
        try:
            req = Request(endpoint, headers={"User-Agent": "VALENCE-VisionCheck"})
            with urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    installed = [m.get("name", "") for m in data.get("models", [])]
                    target = self.model.lower().split(":")[0]
                    if any(target in m.lower() for m in installed):
                        return True, f"Vision model '{self.model}' is available locally."
                    return (
                        False,
                        f"Vision model '{self.model}' is not installed in local Ollama repository. "
                        f"Approved option: run 'ollama pull {self.model}' during online preparation.",
                    )
        except URLError as e:
            return (
                False,
                f"Local Ollama daemon is unreachable on '{self.base_url}': {e}. "
                f"Run 'ollama serve' locally.",
            )
        except Exception as e:
            return False, f"Error checking vision model availability: {e}"

        return False, "Unable to verify vision model status."

    def inspect_image(
        self,
        image_path: Union[str, Path],
        user_prompt: str = "Inspect the image for equipment labels, display readings, and defects.",
    ) -> VisualInterpretation:
        """Processes an inspection image and returns structured observations.

        Raises:
            FileNotFoundError: If image does not exist.
            ValueError: If image is empty or invalid.
        """
        p = Path(image_path)
        b64_image, _ = _read_and_encode_image(p)

        if self._custom_vision_fn is not None:
            return self._custom_vision_fn(p, user_prompt)

        is_avail, reason = self.check_availability()
        if not is_avail:
            logger.warning("Vision processing unavailable (%s). Fallback triggered.", reason)
            return VisualInterpretation(
                observations=[
                    f"Tentative observation: Visual interpretation unavailable ({reason}).",
                    f"Registered image: '{p.name}' ({p.stat().st_size} bytes).",
                ],
                detected_equipment=None,
                is_ambiguous=True,
                raw_description=f"Vision model unavailable: {reason}",
                vision_available=False,
            )

        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": f"User inquiry: {user_prompt}\nProvide concise, factual visual observations.",
            "system": VISION_SYSTEM_PROMPT,
            "images": [b64_image],
            "stream": False,
            # Immediately release VLM memory so it does not compete with text model on 16GB Mac
            "keep_alive": "0m",
            "options": {
                "temperature": 0.1,
            },
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = Request(endpoint, data=req_data, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=90.0) as resp:
                if resp.status == 200:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    raw_text = str(res_json.get("response", "")).strip()
                    return self._parse_vision_response(raw_text, p.name)
                raise RuntimeError(f"Ollama returned HTTP status {resp.status}")
        except Exception as e:
            logger.warning("VLM inference failed on %s: %s", p.name, e)
            return VisualInterpretation(
                observations=[
                    f"Tentative observation: VLM inference failed ({e}).",
                    f"Registered image: '{p.name}'.",
                ],
                detected_equipment=None,
                is_ambiguous=True,
                raw_description=f"VLM failure: {e}",
                vision_available=False,
            )

    def _parse_vision_response(self, raw_text: str, filename: str) -> VisualInterpretation:
        """Parses model response into structured tentative observations and model identity."""
        lines = [line.strip("- *• ") for line in raw_text.splitlines() if line.strip()]
        observations: list[str] = []

        for line in lines:
            if not line:
                continue
            # Format as tentative observation
            if not line.lower().startswith("tentative") and not line.lower().startswith("observed"):
                observations.append(f"Tentative observation: {line}")
            else:
                observations.append(line)

        if not observations:
            observations.append(f"Tentative observation: Inspection of '{filename}' completed with no distinct findings.")

        candidate, is_ambiguous = _extract_model_candidate(raw_text)

        return VisualInterpretation(
            observations=observations,
            detected_equipment=candidate,
            is_ambiguous=is_ambiguous,
            raw_description=raw_text,
            vision_available=True,
        )

