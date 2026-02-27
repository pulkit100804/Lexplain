from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import google.generativeai as genai
from pydantic import BaseModel, Field

from lexplain_ingredient_builder.config import Settings

LOGGER = logging.getLogger(__name__)


class IngredientDraft(BaseModel):
    section: str
    ingredients: list[str] = Field(default_factory=list)


class GeminiIngredientAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    async def generate_ingredients(self, section: str, heading: str, text: str) -> IngredientDraft:
        prompt = self._build_prompt(section=section, heading=heading, text=text)

        for attempt in range(1, self.settings.max_retries + 1):
            try:
                raw = await asyncio.to_thread(self._invoke_model, prompt)
                parsed = self._parse_model_output(raw, section)
                normalized = self._normalize_ingredients(parsed.ingredients)
                return IngredientDraft(section=section, ingredients=normalized)
            except Exception as exc:  # noqa: BLE001
                if attempt >= self.settings.max_retries:
                    LOGGER.exception("Gemini failed for section %s", section)
                    raise
                delay = self.settings.retry_base_delay_seconds * (2 ** (attempt - 1))
                LOGGER.warning(
                    "Gemini call failed for section %s on attempt %s/%s (%s). Retrying in %.2fs",
                    section,
                    attempt,
                    self.settings.max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        return IngredientDraft(section=section, ingredients=[])

    def _invoke_model(self, prompt: str) -> str:
        response = self.model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                candidate_count=1,
                max_output_tokens=500,
                response_mime_type="application/json",
            ),
        )
        return (response.text or "").strip()

    def _build_prompt(self, section: str, heading: str, text: str) -> str:
        return f"""
You are a legal drafting assistant.

Task:
Extract ONLY legally provable ingredients from the IPC section text below.

Hard rules:
1. Ingredients must be directly grounded in the provided section text.
2. Do not hallucinate and do not add external legal doctrines.
3. Keep each ingredient atomic and concise.
4. Return minimum {self.settings.min_ingredients} and maximum {self.settings.max_ingredients} ingredients.
5. Use plain legal language from the text.
6. Return strict JSON only in this shape:
{{"section":"{section}","ingredients":["...","..."]}}

Section number: {section}
Heading: {heading}
Section text:
{text}
""".strip()

    def _parse_model_output(self, raw: str, section: str) -> IngredientDraft:
        if not raw:
            raise ValueError("Model returned empty output")

        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end < 0:
                raise
            data = json.loads(raw[start : end + 1])

        parsed = IngredientDraft.model_validate(data)
        parsed.section = section
        return parsed

    def _normalize_ingredients(self, ingredients: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()

        for ingredient in ingredients:
            normalized = " ".join(ingredient.split()).strip("-• \t\n\r")
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)

        trimmed = deduped[: self.settings.max_ingredients]
        if len(trimmed) < self.settings.min_ingredients:
            return deduped
        return trimmed
