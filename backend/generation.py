"""Local Ollama generation module for VALENCE (Member B).

Generates answers strictly based on retrieved evidence passages.
Ensures source citations map directly to retrieved Evidence items and declares
insufficient evidence whenever documentary support is absent.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Callable, Optional, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen

from contracts import Answer, Evidence, GenerationProtocol
from config import is_loopback_url

logger = logging.getLogger("valence.generation")

DEFAULT_SYSTEM_PROMPT = (
    "You are VALENCE, an expert offline industrial maintenance assistant. "
    "Your objective is to provide clear, easy-to-understand, human-readable answers "
    "to plant technicians and operators using ONLY the provided manual excerpts. "
    "\nResponse Guidelines:"
    "\n1. Human-Readable Synthesis: Do NOT dump raw manual text or chunk snippets verbatim. "
    "Explain the procedure or concept in straightforward, professional, technician-friendly language."
    "\n2. Clear Structure: Use concise bullet points or numbered action steps for procedures. "
    "Highlight key components and safety warnings clearly."
    "\n3. Technical Precision: Keep all technical specifications (torque, pressure, voltage, temperature, "
    "tolerance, pin numbers, part numbers) strictly exact as stated in the excerpts."
    "\n4. Mandatory Citations: Every procedure, recommendation, or technical fact MUST cite its supporting "
    "source identifier in brackets, e.g. [doc#p1#c0]. Every bracketed citation MUST match an available excerpt ID."
    "\n5. Insufficient Evidence: If the provided excerpts do not substantiate the answer, explicitly state: "
    "'Documentary evidence is insufficient to answer this question.'"
)


def _format_context(evidence: Sequence[Evidence]) -> str:
    """Formats retrieved evidence into structured prompt passages."""
    passages: list[str] = []
    for ev in evidence:
        c = ev.chunk
        model_str = f" (Equipment: {c.equipment_model})" if c.equipment_model else ""
        passages.append(
            f"--- Excerpt [{ev.source_id}] (Document: {c.document_id}, Page: {c.page}{model_str}) ---\n"
            f"{c.text}"
        )
    return "\n\n".join(passages)


def _sanitize_citations(text: str, available_evidence: Sequence[Evidence]) -> str:
    """Ensures all bracketed citations [ref] in text correspond to available Evidence source_ids.

    Removes any invented citations not present in available_evidence.
    """
    valid_ids = {e.source_id for e in available_evidence}

    def replace_citation(match: re.Match) -> str:
        ref = match.group(1).strip()
        if ref in valid_ids:
            return f"[{ref}]"
        # If bracket token is not a known source_id, convert brackets to parentheses
        return f"({ref})"

    return re.sub(r"\[([^\]]+)\]", replace_citation, text)


class LocalOllamaGenerator:
    """Generates answers using a locally running Ollama daemon."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: Optional[str] = None,
        generate_fn: Optional[Callable[[str, str], str]] = None,
    ) -> None:
        if not is_loopback_url(base_url):
            raise ValueError(f"Air-gapped constraint violation: base_url must be loopback. Got '{base_url}'")
        self.base_url = base_url.rstrip("/")
        import os
        self.model = model or os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:latest")
        self._custom_generate_fn = generate_fn

    def _call_ollama(self, prompt: str, system: str) -> str:
        """Issues HTTP POST to local Ollama daemon."""
        if self._custom_generate_fn is not None:
            return self._custom_generate_fn(prompt, system)

        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for technical fidelity
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = Request(endpoint, data=data, headers={"Content-Type": "application/json"})

        try:
            with urlopen(req, timeout=120.0) as resp:
                if resp.status == 200:
                    result = json.loads(resp.read().decode("utf-8"))
                    return str(result.get("response", "")).strip()
                raise RuntimeError(f"Ollama returned HTTP status {resp.status}")
        except URLError as e:
            raise RuntimeError(
                f"Cannot connect to local Ollama daemon at '{self.base_url}': {e}. "
                f"Ensure 'ollama serve' is running locally."
            ) from e

    def answer_with_evidence(
        self,
        question: str,
        evidence: Sequence[Evidence],
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Synthesizes an Answer grounded in provided Evidence items.

        Returns Answer with insufficient_evidence=True if evidence is empty.
        """
        if not evidence:
            model_info = f" for equipment '{equipment_model}'" if equipment_model else ""
            return Answer(
                text=f"Insufficient documentary evidence found{model_info} to answer the question: '{question}'.",
                evidence=[],
                insufficient_evidence=True,
                observations=[],
            )

        context_str = _format_context(evidence)
        model_context = f"\nTarget Equipment: {equipment_model}" if equipment_model else ""
        prompt = (
            f"User Question: {question}{model_context}\n\n"
            f"Available Documentation Excerpts:\n"
            f"{context_str}\n\n"
            f"Instructions:\n"
            f"1. Synthesize a clear, human-readable response in plain, professional technician language.\n"
            f"2. Ground your answer strictly in the excerpts above, citing the corresponding source ID in brackets (e.g. [{evidence[0].source_id}]).\n"
            f"3. If the provided excerpts contain sufficient evidence to answer the question, give the answer directly with citations. Do NOT add any insufficient evidence disclaimer.\n"
            f"4. Only if the excerpts genuinely do NOT substantiate the answer, state: 'Documentary evidence is insufficient to answer this question.'"
        )

        raw_response = self._call_ollama(prompt, DEFAULT_SYSTEM_PROMPT)

        # Sanitize citations so text conforms strictly to contracts.py invariants
        sanitized_text = _sanitize_citations(raw_response, evidence)

        # Check if the LLM itself declared insufficient evidence
        insufficient = False
        lower_resp = sanitized_text.lower()
        if "insufficient evidence" in lower_resp or "does not contain" in lower_resp:
            insufficient = True

        # Ensure at least the primary citation is referenced if not declared insufficient
        if not insufficient and not any(f"[{e.source_id}]" in sanitized_text for e in evidence):
            sanitized_text = f"According to [{evidence[0].source_id}]: {sanitized_text}"

        ans = Answer(
            text=sanitized_text,
            evidence=list(evidence),
            insufficient_evidence=insufficient,
            observations=[],
        )
        return ans

