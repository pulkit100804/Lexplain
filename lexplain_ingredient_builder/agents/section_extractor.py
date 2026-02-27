from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


class SectionPayload(BaseModel):
    section: str = Field(..., description="Normalized numeric section identifier")
    heading: str
    text: str


class SectionExtractorAgent:
    """Reads nested IPC JSON and emits normalized section payloads."""

    _section_pattern = re.compile(r"(\d+[A-Za-z]?)")

    def extract(self, input_json_path: Path) -> list[SectionPayload]:
        LOGGER.info("Loading input JSON from %s", input_json_path)
        with input_json_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)

        extracted: list[SectionPayload] = []
        self._walk(data, extracted)

        extracted.sort(key=lambda payload: self._section_sort_key(payload.section))
        LOGGER.info("Extracted %s sections", len(extracted))
        return extracted

    def _walk(self, node: Any, extracted: list[SectionPayload]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if self._looks_like_section_dict(key, value):
                    normalized = self._normalize_section_number(key)
                    paragraphs = value.get("paragraphs", {})
                    full_text = self._merge_paragraphs(paragraphs)
                    payload = SectionPayload(
                        section=normalized,
                        heading=str(value.get("heading", "")).strip(),
                        text=full_text,
                    )
                    if payload.text:
                        extracted.append(payload)
                    else:
                        LOGGER.warning(
                            "Skipping section %s because no textual content found", normalized
                        )
                else:
                    self._walk(value, extracted)
        elif isinstance(node, list):
            for item in node:
                self._walk(item, extracted)

    def _looks_like_section_dict(self, key: str, value: Any) -> bool:
        if not isinstance(key, str) or not isinstance(value, dict):
            return False
        if "paragraphs" in value:
            return self._section_pattern.search(key) is not None
        return False

    def _normalize_section_number(self, raw: str) -> str:
        match = self._section_pattern.search(raw)
        if not match:
            return raw.strip().rstrip(".")
        return match.group(1)

    def _merge_paragraphs(self, paragraphs: Any) -> str:
        if isinstance(paragraphs, dict):
            try:
                ordered_keys = sorted(paragraphs.keys(), key=lambda k: int(str(k)))
            except ValueError:
                ordered_keys = sorted(paragraphs.keys(), key=lambda k: str(k))
            chunks = [str(paragraphs[k]).strip() for k in ordered_keys]
            return " ".join(chunk for chunk in chunks if chunk)
        if isinstance(paragraphs, list):
            return " ".join(str(item).strip() for item in paragraphs if str(item).strip())
        return ""

    def _section_sort_key(self, section: str) -> tuple[int, str]:
        number = "".join(ch for ch in section if ch.isdigit())
        suffix = "".join(ch for ch in section if ch.isalpha())
        return (int(number) if number else 10**9, suffix)
