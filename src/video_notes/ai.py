from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv

from video_notes.models import AIConfig


class AIProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    def __init__(self, config: AIConfig, api_key: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Az OpenAI csomag nincs telepítve. Futtasd: pip install -e \".[ai]\""
            ) from exc

        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY hiányzik. Add hozzá a .env fájlhoz."
            )

        self._client = OpenAI(api_key=key)
        self._config = config

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._config.model,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Az AI üres választ adott.")
        return content.strip()


def load_prompt(name: str, prompts_dir: Path | None = None) -> str:
    directory = prompts_dir or Path("prompts")
    path = directory / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"A prompt sablon nem található: {path}")
    return path.read_text(encoding="utf-8")


def create_ai_provider(config: AIConfig) -> AIProvider:
    load_dotenv()
    if config.provider == "openai":
        return OpenAIProvider(config)
    raise RuntimeError(f"Ismeretlen AI provider: {config.provider}")


def extract_json_array(text: str) -> list[dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Az AI válasz nem érvényes JSON: {text[:200]}") from exc

    if not isinstance(data, list):
        raise RuntimeError("Az AI válasznak JSON tömbnek kell lennie.")
    return data
