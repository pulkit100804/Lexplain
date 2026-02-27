from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


class SectionIngredients(BaseModel):
    section: str
    heading: str
    ingredients: list[str] = Field(default_factory=list)


class IngredientDatabaseBuilder:
    def build(self, sections: list[SectionIngredients]) -> dict:
        ipc: dict[str, dict] = {}
        for item in sorted(sections, key=self._sort_key):
            ipc[item.section] = {
                "heading": item.heading,
                "ingredients": item.ingredients,
            }
        return {"IPC": ipc}

    def write(self, payload: dict, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        LOGGER.info("Wrote ingredient database to %s", output_path)

    def _sort_key(self, item: SectionIngredients) -> tuple[int, str]:
        num = "".join(ch for ch in item.section if ch.isdigit())
        suffix = "".join(ch for ch in item.section if ch.isalpha())
        return (int(num) if num else 10**9, suffix)
