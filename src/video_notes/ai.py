from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv

from video_notes.models import AIConfig

SUPPORTED_PROVIDERS: tuple[str, ...] = ("mistral", "gemini", "openai")

DEFAULT_MODELS: dict[str, str] = {
    "mistral": "mistral-small-latest",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o",
}

PROVIDER_ENV_KEYS: dict[str, str] = {
    "mistral": "MISTRAL_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}

GEMINI_API_KEY_ALIASES: tuple[str, ...] = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


class AIProvider(ABC):
    name: str

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class MistralProvider(AIProvider):
    name = "mistral"

    def __init__(self, config: AIConfig, api_key: str | None = None) -> None:
        try:
            from mistralai.client import Mistral
        except ImportError as exc:
            raise RuntimeError(
                "A mistralai csomag nincs telepítve. Futtasd: pip install -e \".[ai]\""
            ) from exc

        key = api_key or os.getenv(PROVIDER_ENV_KEYS["mistral"])
        if not key:
            raise RuntimeError(
                "MISTRAL_API_KEY hiányzik. Add hozzá a .env fájlhoz."
            )

        self._client = Mistral(api_key=key)
        self._config = config

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.complete(
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
            raise RuntimeError("A Mistral AI üres választ adott.")
        return content.strip()


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, config: AIConfig, api_key: str | None = None) -> None:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise RuntimeError(
                "A google-genai csomag nincs telepítve. Futtasd: pip install -e \".[ai]\""
            ) from exc

        key = api_key
        if not key:
            for env_name in GEMINI_API_KEY_ALIASES:
                key = os.getenv(env_name)
                if key:
                    break
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY vagy GOOGLE_API_KEY hiányzik. Add hozzá a .env fájlhoz."
            )

        self._client = genai.Client(api_key=key)
        self._config = config
        self._genai_types = genai_types

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._config.model,
            contents=user_prompt,
            config=self._genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self._config.temperature,
                max_output_tokens=self._config.max_tokens,
            ),
        )
        content = response.text
        if not content:
            raise RuntimeError("A Gemini AI üres választ adott.")
        return content.strip()


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, config: AIConfig, api_key: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Az OpenAI csomag nincs telepítve. Futtasd: pip install -e \".[ai]\""
            ) from exc

        key = api_key or os.getenv(PROVIDER_ENV_KEYS["openai"])
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
            raise RuntimeError("Az OpenAI üres választ adott.")
        return content.strip()


def apply_provider_defaults(
    config: AIConfig,
    provider: str | None = None,
    model: str | None = None,
) -> AIConfig:
    selected = (provider or config.provider).lower()
    if selected not in SUPPORTED_PROVIDERS:
        available = ", ".join(SUPPORTED_PROVIDERS)
        raise RuntimeError(f"Ismeretlen provider: {selected}. Elérhető: {available}")

    selected_model = model or config.model
    if provider and not model and selected != config.provider.lower():
        selected_model = DEFAULT_MODELS[selected]

    return AIConfig(
        provider=selected,
        model=selected_model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


def load_prompt(name: str, prompts_dir: Path | None = None) -> str:
    directory = prompts_dir or Path("prompts")
    path = directory / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"A prompt sablon nem található: {path}")
    return path.read_text(encoding="utf-8")


def create_ai_provider(config: AIConfig) -> AIProvider:
    load_dotenv()
    normalized = apply_provider_defaults(config)

    if normalized.provider == "mistral":
        return MistralProvider(normalized)
    if normalized.provider == "gemini":
        return GeminiProvider(normalized)
    if normalized.provider == "openai":
        return OpenAIProvider(normalized)

    available = ", ".join(SUPPORTED_PROVIDERS)
    raise RuntimeError(f"Ismeretlen AI provider: {config.provider}. Elérhető: {available}")


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


def extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Az AI válasz nem érvényes JSON: {text[:200]}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Az AI válasznak JSON objektumnak kell lennie.")
    return data
