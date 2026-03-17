from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from lexplain_ingredient_builder.agents.gemini_agent import IngredientItem, SectionIngredientsDraft
from lexplain_ingredient_builder.config import Settings

LOGGER = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
SENTENCE_SPLIT_PATTERN = re.compile(r"[.;!?]\s+")


class RejectedIngredient(BaseModel):
    ingredient_id: str
    name: str
    similarity: float


class IngredientValidationResult(BaseModel):
    section_id: str
    ingredients: list[IngredientItem] = Field(default_factory=list)
    removed: list[RejectedIngredient] = Field(default_factory=list)


class IngredientValidationAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate(self, draft: SectionIngredientsDraft, text: str) -> IngredientValidationResult:
        retained: list[IngredientItem] = []
        removed: list[RejectedIngredient] = []

        for ingredient in draft.ingredients:
            probe = f"{ingredient.description} {' '.join(ingredient.match_patterns)}"
            similarity = self._semantic_similarity(probe, text)
            if similarity >= self.settings.similarity_threshold:
                retained.append(ingredient)
            else:
                removed.append(
                    RejectedIngredient(
                        ingredient_id=ingredient.ingredient_id,
                        name=ingredient.name,
                        similarity=similarity,
                    )
                )

        if len(retained) < self.settings.min_ingredients:
            LOGGER.warning(
                "Section %s retained %s ingredient(s), below configured minimum %s",
                draft.section_id,
                len(retained),
                self.settings.min_ingredients,
            )

        return IngredientValidationResult(section_id=draft.section_id, ingredients=retained, removed=removed)

    def _semantic_similarity(self, phrase: str, text: str) -> float:
        phrase_tokens = set(self._tokens(phrase))
        if not phrase_tokens:
            return 0.0

        segments = [seg.strip() for seg in SENTENCE_SPLIT_PATTERN.split(text) if seg.strip()]
        if not segments:
            segments = [text]

        best_score = 0.0
        phrase_lower = phrase.lower()

        for segment in segments:
            segment_tokens = set(self._tokens(segment))
            if not segment_tokens:
                continue
            token_coverage = len(phrase_tokens & segment_tokens) / len(phrase_tokens)
            sequence_ratio = SequenceMatcher(None, phrase_lower, segment.lower()).ratio()
            containment_bonus = 1.0 if phrase_lower in segment.lower() else 0.0
            score = (0.70 * token_coverage) + (0.20 * sequence_ratio) + (0.10 * containment_bonus)
            best_score = max(best_score, score)

        return round(min(max(best_score, 0.0), 1.0), 4)

    def _tokens(self, value: str) -> list[str]:
        return TOKEN_PATTERN.findall(value.lower())
