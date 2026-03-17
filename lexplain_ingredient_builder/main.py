from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from lexplain_ingredient_builder.agents.builder_agent import IngredientDatabaseBuilder, SectionIngredientRecord
from lexplain_ingredient_builder.agents.gemini_agent import GeminiIngredientAgent
from lexplain_ingredient_builder.agents.section_extractor import SectionExtractorAgent
from lexplain_ingredient_builder.agents.validator_agent import IngredientValidationAgent
from lexplain_ingredient_builder.config import get_settings


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def process_sections(input_path: Path, output_path: Path) -> None:
    settings = get_settings()
    extractor = SectionExtractorAgent()
    gemini_agent = GeminiIngredientAgent(settings=settings)
    validator_agent = IngredientValidationAgent(settings=settings)
    builder_agent = IngredientDatabaseBuilder()

    extracted = extractor.extract(input_path)
    logging.info("Starting async processing for %s section(s)", len(extracted))

    semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def process_single(item) -> SectionIngredientRecord:
        async with semaphore:
            draft = await gemini_agent.generate_ingredients(
                section_id=item.section_id,
                heading=item.heading,
                text=item.text,
            )
            validated = validator_agent.validate(draft=draft, text=item.text)

            final_draft = draft.model_copy(deep=True)
            final_draft.ingredients = validated.ingredients

            if final_draft.ingredients:
                total = round(sum(ing.weight for ing in final_draft.ingredients), 2)
                if total != 1.0:
                    # deterministic normalize
                    each = round(1.0 / len(final_draft.ingredients), 2)
                    for ing in final_draft.ingredients[:-1]:
                        ing.weight = each
                    final_draft.ingredients[-1].weight = round(
                        1.0 - sum(i.weight for i in final_draft.ingredients[:-1]), 2
                    )
                final_draft.match_patterns = gemini_agent._derive_section_patterns(final_draft.ingredients)

            return SectionIngredientRecord.model_validate(final_draft.model_dump())

    tasks = [asyncio.create_task(process_single(item)) for item in extracted]
    processed = await asyncio.gather(*tasks)

    payload = builder_agent.build(processed)
    builder_agent.write(payload=payload, output_path=output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lexplain Ingredient Builder")
    parser.add_argument("--input", type=Path, required=True, help="Path to input IPC JSON file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ingredients_ipc.json"),
        help="Output path for generated ingredient JSON",
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    asyncio.run(process_sections(args.input, args.output))


if __name__ == "__main__":
    main()
