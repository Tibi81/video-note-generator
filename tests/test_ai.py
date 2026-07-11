import pytest

from video_notes.ai import (
    DEFAULT_MODELS,
    MistralProvider,
    OpenAIProvider,
    apply_provider_defaults,
    create_ai_provider,
    extract_json_array,
    extract_json_object,
)
from video_notes.models import AIConfig


def test_apply_provider_defaults_switches_model_for_mistral():
    config = AIConfig(provider="openai", model="gpt-4o")
    result = apply_provider_defaults(config, provider="mistral")

    assert result.provider == "mistral"
    assert result.model == DEFAULT_MODELS["mistral"]


def test_apply_provider_defaults_keeps_explicit_model():
    config = AIConfig(provider="openai", model="gpt-4o")
    result = apply_provider_defaults(config, provider="mistral", model="mistral-large-latest")

    assert result.provider == "mistral"
    assert result.model == "mistral-large-latest"


def test_apply_provider_defaults_unknown_provider():
    config = AIConfig()
    with pytest.raises(RuntimeError, match="Ismeretlen provider"):
        apply_provider_defaults(config, provider="unknown")


def test_create_ai_provider_mistral_missing_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setenv("MISTRAL_API_KEY", "")
    config = AIConfig(provider="mistral")

    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        create_ai_provider(config)


def test_mistral_provider_complete(monkeypatch):
    class FakeChoice:
        message = type("Message", (), {"content": "  [{\"title\": \"Teszt\", \"start\": \"00:01:00\"}]  "})()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeChat:
        def complete(self, **kwargs):
            assert kwargs["model"] == "mistral-small-latest"
            return FakeResponse()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        "video_notes.ai.MistralProvider.__init__",
        lambda self, config, api_key=None: setattr(self, "_client", FakeClient())
        or setattr(self, "_config", config),
    )

    provider = MistralProvider(AIConfig(provider="mistral"))
    result = provider.complete("system", "user")

    assert "Teszt" in result


def test_openai_provider_complete(monkeypatch):
    class FakeMessage:
        content = "hello"

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        "video_notes.ai.OpenAIProvider.__init__",
        lambda self, config, api_key=None: setattr(self, "_client", FakeClient())
        or setattr(self, "_config", config),
    )

    provider = OpenAIProvider(AIConfig(provider="openai"))
    assert provider.complete("system", "user") == "hello"


def test_extract_json_array_strips_markdown_fence():
    raw = '```json\n[{"title": "A", "start": "00:00:10"}]\n```'
    data = extract_json_array(raw)
    assert data[0]["title"] == "A"


def test_extract_json_object():
    raw = '```json\n{"summary": "Teszt", "key_points": ["a"]}\n```'
    data = extract_json_object(raw)
    assert data["summary"] == "Teszt"


def test_render_prompt_handles_braces_in_transcript():
    from video_notes.ai import render_prompt

    template = "Title: $title\nBody:\n$transcript"
    result = render_prompt(
        template,
        title="JSON példa",
        transcript='const obj = {"key": "value"}; // CSS: .class { color: red }',
    )
    assert '{"key": "value"}' in result
    assert ".class { color: red }" in result


def test_render_prompt_substitutes_domain_hints():
    from video_notes.ai import prompt_context_from_settings, render_prompt

    settings = {
        "project": {
            "domain_hints": "Python, pytest",
            "practice_context": "backend workshop",
            "chapters_per_minutes": "5",
        }
    }
    context = prompt_context_from_settings(settings)
    result = render_prompt(
        "Hints: $domain_hints\nContext: $practice_context\nRate: $chapters_per_minutes",
        **context,
    )
    assert "Python, pytest" in result
    assert "backend workshop" in result
    assert "5" in result


def test_apply_provider_defaults_gemini():
    config = AIConfig(provider="mistral")
    result = apply_provider_defaults(config, provider="gemini")
    assert result.provider == "gemini"
    assert result.model == DEFAULT_MODELS["gemini"]
