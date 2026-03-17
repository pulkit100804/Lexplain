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
    section_id: str
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
                    section_number = self._normalize_section_number(key)
                    full_text = self._merge_paragraphs(value.get("paragraphs", {}))
                    payload = SectionPayload(
                        section=section_number,
                        section_id=f"IPC_{section_number}",
                        heading=str(value.get("heading", "")).strip().strip("."),
                        text=full_text,
                    )
                    if payload.text:
                        extracted.append(payload)
                    else:
                        LOGGER.warning("Skipping section %s because no textual content found", section_number)
                else:
                    self._walk(value, extracted)
        elif isinstance(node, list):
            for item in node:
                self._walk(item, extracted)

    def _looks_like_section_dict(self, key: str, value: Any) -> bool:
        return isinstance(key, str) and isinstance(value, dict) and "paragraphs" in value and bool(self._section_pattern.search(key))

    def _normalize_section_number(self, raw: str) -> str:
        match = self._section_pattern.search(raw)
        if not match:
            return raw.strip().rstrip(".")
        return match.group(1)

    def _merge_paragraphs(self, paragraphs: Any) -> str:
        chunks = self._flatten_text(paragraphs)
        return " ".join(part for part in chunks if part).strip()

    def _flatten_text(self, node: Any) -> list[str]:
        if isinstance(node, str):
            return [" ".join(node.split())]
        if isinstance(node, list):
            out: list[str] = []
            for item in node:
                out.extend(self._flatten_text(item))
            return out
        if isinstance(node, dict):
            out: list[str] = []
            if "text" in node:
                out.extend(self._flatten_text(node["text"]))
            if "contains" in node:
                out.extend(self._flatten_text(node["contains"]))
            numeric_like = [k for k in node.keys() if str(k).isdigit()]
            if numeric_like:
                for key in sorted(numeric_like, key=lambda x: int(str(x))):
                    out.extend(self._flatten_text(node[key]))
            else:
                for key in sorted(node.keys(), key=str):
                    if key in {"text", "contains"}:
                        continue
                    out.extend(self._flatten_text(node[key]))
            return out
        return []

    def _section_sort_key(self, section: str) -> tuple[int, str]:
        number = "".join(ch for ch in section if ch.isdigit())
        suffix = "".join(ch for ch in section if ch.isalpha())
        return (int(number) if number else 10**9, suffix)
