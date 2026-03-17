from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from lexplain_ingredient_builder.agents.gemini_agent import IngredientItem

LOGGER = logging.getLogger(__name__)


class SectionIngredientRecord(BaseModel):
    section_id: str
    name: str
    section_type: str = "substantive"
    ingredients: list[IngredientItem] = Field(default_factory=list)
    match_patterns: list[str] = Field(default_factory=list)
    weight: float = 1.0


class IngredientDatabaseBuilder:
    def build(self, sections: list[SectionIngredientRecord]) -> list[dict]:
        return [item.model_dump() for item in sorted(sections, key=self._sort_key)]

    def write(self, payload: list[dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        LOGGER.info("Wrote ingredient database to %s", output_path)

    def _sort_key(self, item: SectionIngredientRecord) -> tuple[int, str]:
        raw = item.section_id.replace("IPC_", "")
        num = "".join(ch for ch in raw if ch.isdigit())
        suffix = "".join(ch for ch in raw if ch.isalpha())
        return (int(num) if num else 10**9, suffix)
