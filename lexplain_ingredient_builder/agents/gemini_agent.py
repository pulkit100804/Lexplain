from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import google.generativeai as genai
from pydantic import BaseModel, Field

from lexplain_ingredient_builder.config import Settings

LOGGER = logging.getLogger(__name__)


class IngredientItem(BaseModel):
    ingredient_id: str
    name: str
    description: str
    match_patterns: list[str] = Field(default_factory=list)
    weight: float = 0.0


class SectionIngredientsDraft(BaseModel):
    section_id: str
    name: str
    section_type: str
    ingredients: list[IngredientItem] = Field(default_factory=list)
    match_patterns: list[str] = Field(default_factory=list)
    weight: float = 1.0


class GeminiIngredientAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    async def generate_ingredients(self, section_id: str, heading: str, text: str) -> SectionIngredientsDraft:
        prompt = self._build_prompt(section_id=section_id, heading=heading, text=text)

        for attempt in range(1, self.settings.max_retries + 1):
            try:
                raw = await asyncio.to_thread(self._invoke_model, prompt)
                parsed = self._parse_model_output(raw)
                return self._normalize_output(parsed, section_id, heading)
            except Exception as exc:  # noqa: BLE001
                if attempt >= self.settings.max_retries:
                    LOGGER.exception("Gemini failed for section %s", section_id)
                    raise
                delay = self.settings.retry_base_delay_seconds * (2 ** (attempt - 1))
                LOGGER.warning(
                    "Gemini call failed for section %s on attempt %s/%s (%s). Retrying in %.2fs",
                    section_id,
                    attempt,
                    self.settings.max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError(f"Unable to generate ingredients for {section_id}")

    def _invoke_model(self, prompt: str) -> str:
        response = self.model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                candidate_count=1,
                max_output_tokens=1200,
                response_mime_type="application/json",
            ),
        )
        return (response.text or "").strip()

    def _build_prompt(self, section_id: str, heading: str, text: str) -> str:
        return f"""
You are a legal ingredient extraction engine.

Output strict JSON only for this schema:
{{
  "section_id": "{section_id}",
  "name": "{heading}",
  "section_type": "{self.settings.section_type}",
  "ingredients": [
    {{
      "ingredient_id": "{section_id}_I1",
      "name": "snake_case_name",
      "description": "Legally provable element from section text",
      "match_patterns": ["token1", "token2"],
      "weight": 0.5
    }}
  ],
  "match_patterns": ["token1", "token2"],
  "weight": 1.0
}}

Rules:
1) Use only facts stated in the section text.
2) Minimum {self.settings.min_ingredients} and maximum {self.settings.max_ingredients} ingredients.
3) Ingredients must be atomic and legally provable.
4) ingredient name must be snake_case.
5) Each ingredient must include 3 to {self.settings.max_patterns_per_ingredient} match_patterns.
6) Ingredient weights must sum to exactly 1.0 (rounded to 2 decimals).
7) Top-level weight must be 1.0.
8) Do not include markdown or explanation.

Section heading: {heading}
Section text: {text}
""".strip()

    def _parse_model_output(self, raw: str) -> SectionIngredientsDraft:
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
        return SectionIngredientsDraft.model_validate(data)

    def _normalize_output(self, draft: SectionIngredientsDraft, section_id: str, heading: str) -> SectionIngredientsDraft:
        draft.section_id = section_id
        draft.name = heading
        draft.section_type = self.settings.section_type
        draft.weight = 1.0

        for idx, ingredient in enumerate(draft.ingredients, start=1):
            ingredient.ingredient_id = f"{section_id}_I{idx}"
            ingredient.name = self._to_snake_case(ingredient.name)
            ingredient.match_patterns = self._normalize_patterns(ingredient.match_patterns)
            ingredient.description = " ".join(ingredient.description.split()).strip()

        draft.ingredients = draft.ingredients[: self.settings.max_ingredients]
        if len(draft.ingredients) < self.settings.min_ingredients:
            raise ValueError(f"Model returned {len(draft.ingredients)} ingredients; minimum is {self.settings.min_ingredients}")

        self._rebalance_weights(draft.ingredients)
        draft.match_patterns = self._derive_section_patterns(draft.ingredients)
        return draft

    def _to_snake_case(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
        return re.sub(r"_+", "_", cleaned).strip("_") or "ingredient"

    def _normalize_patterns(self, patterns: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for pattern in patterns:
            token = pattern.strip().lower()
            token = re.sub(r"\s+", " ", token)
            if not token or token in seen:
                continue
            seen.add(token)
            normalized.append(token)
        return normalized[: self.settings.max_patterns_per_ingredient]

    def _rebalance_weights(self, ingredients: list[IngredientItem]) -> None:
        count = len(ingredients)
        if count == 0:
            return
        base = round(1.0 / count, 2)
        weights = [base] * count
        weights[-1] = round(1.0 - sum(weights[:-1]), 2)
        for i, item in enumerate(ingredients):
            item.weight = weights[i]

    def _derive_section_patterns(self, ingredients: list[IngredientItem]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for ingredient in ingredients:
            for pattern in ingredient.match_patterns:
                if pattern in seen:
                    continue
                seen.add(pattern)
                merged.append(pattern)
        return merged[:6]
