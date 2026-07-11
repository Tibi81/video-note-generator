from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from string import Template
from typing import TypeVar

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
        try:
            response = self._client.chat.complete(
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:  # noqa: BLE001 - normalize any SDK error
            raise RuntimeError(f"Mistral API hiba: {exc}") from exc
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
        try:
            response = self._client.models.generate_content(
                model=self._config.model,
                contents=user_prompt,
                config=self._genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self._config.temperature,
                    max_output_tokens=self._config.max_tokens,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - normalize any SDK error
            raise RuntimeError(f"Gemini API hiba: {exc}") from exc
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
        try:
            response = self._client.chat.completions.create(
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:  # noqa: BLE001 - normalize any SDK error
            raise RuntimeError(f"OpenAI API hiba: {exc}") from exc
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


def render_prompt(template: str, **values: str) -> str:
    """Prompt sablon kitöltése — $placeholder szintaxis, biztonságos { } karakterekkel."""
    return Template(template).substitute(**values)


def prompt_context_from_settings(settings: dict) -> dict[str, str]:
    project = settings.get("project", {})
    return {
        "domain_hints": project.get(
            "domain_hints",
            "a videó témájához illő konkrét szakkifejezések",
        ),
        "practice_context": project.get(
            "practice_context",
            "a workshop témájához illő gyakorlati környezet",
        ),
        "chapters_per_minutes": str(project.get("chapters_per_minutes", "3-4")),
    }


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


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


def _invalid_json_message(raw_text: str) -> str:
    limit = 600
    length = len(raw_text)
    if length <= limit:
        snippet = raw_text
    else:
        head = raw_text[: limit // 2]
        tail = raw_text[-limit // 2 :]
        snippet = f"{head}\n…[{length - limit} karakter kimaradt]…\n{tail}"
    return f"Az AI válasz nem érvényes JSON ({length} karakter):\n{snippet}"


def _json_cut_candidates(text: str) -> list[tuple[int, list[str]]]:
    """Minden pontot összegyűjt, ahol a szöveg lezárt string vagy lezárt {}/[] után áll.
    Ezek jelöltek a csonka JSON válasz biztonságos levágási pontjaira."""
    in_string = False
    escape = False
    stack: list[str] = []
    candidates: list[tuple[int, list[str]]] = []

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
                candidates.append((i + 1, list(stack)))
            continue

        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            candidates.append((i + 1, list(stack)))

    return candidates


def repair_truncated_json(text: str) -> str | None:
    """Csonka (token-limit miatt félbeszakadt) JSON válasz javítási kísérlete.

    A modell válasza néha a generálás közben megszakad (pl. max_tokens elérése).
    Ez a függvény megkeresi az utolsó teljesen lezárt elemet, és onnan zárja le
    a nyitott zárójeleket/kapcsos zárójeleket, elhagyva a befejezetlen töredéket.
    """
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return None

    closers = {"{": "}", "[": "]"}
    candidates = _json_cut_candidates(stripped)

    for cut_index, stack_at_cut in reversed(candidates):
        if not stack_at_cut:
            # Nincs mit levágni — a szöveg végén helyesen zárt, más a hiba oka.
            continue
        truncated = re.sub(r",\s*$", "", stripped[:cut_index])
        repaired = truncated + "".join(closers[c] for c in reversed(stack_at_cut))
        if repaired == stripped:
            continue
        try:
            json.loads(repaired)
        except json.JSONDecodeError:
            continue
        return repaired

    return None


def extract_json_array(text: str) -> list[dict]:
    cleaned = _strip_code_fence(text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = repair_truncated_json(cleaned)
        if repaired is None:
            raise RuntimeError(_invalid_json_message(text)) from None
        data = json.loads(repaired)

    if not isinstance(data, list):
        raise RuntimeError("Az AI válasznak JSON tömbnek kell lennie.")
    return data


def extract_json_object(text: str) -> dict:
    cleaned = _strip_code_fence(text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = repair_truncated_json(cleaned)
        if repaired is None:
            raise RuntimeError(_invalid_json_message(text)) from None
        data = json.loads(repaired)

    if not isinstance(data, dict):
        raise RuntimeError("Az AI válasznak JSON objektumnak kell lennie.")
    return data


T = TypeVar("T")


def complete_and_parse_with_retry(
    provider: AIProvider,
    system_prompt: str,
    user_prompt: str,
    parse: Callable[[str], T],
    max_retries: int = 2,
) -> T:
    """Provider hívása + válasz feldolgozása, hibánál (pl. csonka JSON) újrapróbálással.

    Az LLM válaszok nem determinisztikusak — egy csonkolt/hibás JSON válasz gyakran
    egyszerű újrapróbálkozással (új generálással) megoldódik, anélkül hogy az egész
    (akár többórás) pipeline-t újra kellene futtatni egy elszigetelt hiba miatt.
    """
    last_error: RuntimeError | None = None
    for _ in range(max_retries + 1):
        try:
            raw = provider.complete(system_prompt=system_prompt, user_prompt=user_prompt)
            return parse(raw)
        except RuntimeError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error
