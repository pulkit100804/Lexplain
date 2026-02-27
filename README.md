# Lexplain Ingredient Builder

Production-ready multi-agent pipeline to generate legally provable IPC ingredients from structured IPC JSON.

## Features
- Multi-agent architecture:
  - `SectionExtractorAgent`
  - `GeminiIngredientAgent`
  - `IngredientValidationAgent`
  - `IngredientDatabaseBuilder`
- Async parallel processing with bounded concurrency
- Gemini API integration with exponential backoff retries
- Deterministic generation configuration (`temperature=0`)
- JSON-safe output with stable ordering
- Pydantic validation across pipeline boundaries
- Structured logging for observability

## Input format
Nested IPC JSON (Act -> Chapters -> Sections -> paragraphs). The extractor scans recursively and finds section dictionaries containing `paragraphs`.

## Output format
`ingredients_ipc.json`:

```json
{
  "IPC": {
    "23": {
      "heading": "Wrongful Gain",
      "ingredients": [
        "Property involved",
        "Gain obtained",
        "Unlawful means used",
        "No legal entitlement"
      ]
    }
  }
}
```

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:
```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
MAX_CONCURRENCY=20
```

## Run
```bash
python -m lexplain_ingredient_builder.main --input ipc_sections.json --output ingredients_ipc.json
```

## Performance guidance
For ~500 sections:
- Set `MAX_CONCURRENCY` based on quota/rate-limit constraints (20–40 typical)
- Keep retries enabled for transient failures
- Use stable model choice (`gemini-1.5-flash`) for speed/cost balance
