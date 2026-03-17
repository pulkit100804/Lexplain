# Lexplain Ingredient Builder

Production-ready multi-agent pipeline to generate legally provable IPC ingredients from nested IPC JSON.

## Output shape (exact)
The system now writes `ingredients_ipc.json` as a list of objects in this format:

```json
[
  {
    "section_id": "IPC_420",
    "name": "Cheating and dishonestly inducing delivery of property",
    "section_type": "substantive",
    "ingredients": [
      {
        "ingredient_id": "IPC_420_I1",
        "name": "deceptive_act",
        "description": "The accused made a false or deceptive representation",
        "match_patterns": ["fraud", "cheat", "deceiv"],
        "weight": 0.34
      }
    ],
    "match_patterns": ["fraud", "cheat", "deceiv"],
    "weight": 1.0
  }
]
```

## Agents
- `SectionExtractorAgent`: recursively parses complex nested `paragraphs` including `text` + `contains` blocks.
- `GeminiIngredientAgent`: calls Gemini (`gemini-2.0-pro` default), enforces strict schema, deterministic settings, retries.
- `IngredientValidationAgent`: removes ungrounded ingredients using deterministic semantic similarity (threshold default `0.6`).
- `IngredientDatabaseBuilder`: writes final JSON-safe ordered output.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:
```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-pro
MAX_CONCURRENCY=20
SIMILARITY_THRESHOLD=0.6
```

## Run
```bash
python -m lexplain_ingredient_builder.main --input ipc_sections.json --output ingredients_ipc.json
```

## Notes
- Handles section names like `Section 228A.` and produces `section_id: IPC_228A`.
- Designed to process large batches (e.g., 500 sections) with async bounded concurrency.
