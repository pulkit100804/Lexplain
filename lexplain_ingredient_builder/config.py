from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    gemini_api_key: str = Field(..., min_length=10)
    gemini_model: str = Field(default="gemini-2.0-pro")
    section_type: str = Field(default="substantive")
    max_ingredients: int = Field(default=6, ge=2, le=10)
    min_ingredients: int = Field(default=2, ge=1, le=6)
    max_patterns_per_ingredient: int = Field(default=5, ge=2, le=8)
    similarity_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    max_concurrency: int = Field(default=20, ge=1, le=200)
    max_retries: int = Field(default=4, ge=1, le=10)
    retry_base_delay_seconds: float = Field(default=1.0, ge=0.1, le=30.0)

    @field_validator("gemini_api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("GEMINI_API_KEY cannot be empty")
        return value


def _load_dotenv() -> None:
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv()
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-pro"),
        section_type=os.getenv("SECTION_TYPE", "substantive"),
        max_ingredients=int(os.getenv("MAX_INGREDIENTS", "6")),
        min_ingredients=int(os.getenv("MIN_INGREDIENTS", "2")),
        max_patterns_per_ingredient=int(os.getenv("MAX_PATTERNS_PER_INGREDIENT", "5")),
        similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.6")),
        max_concurrency=int(os.getenv("MAX_CONCURRENCY", "20")),
        max_retries=int(os.getenv("MAX_RETRIES", "4")),
        retry_base_delay_seconds=float(os.getenv("RETRY_BASE_DELAY_SECONDS", "1.0")),
    )
