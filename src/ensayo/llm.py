"""LLM provider abstraction (spec §8).

A small, synchronous provider interface used by content generation. ``stub`` needs
no keys and powers offline generation; real providers call out via httpx. The
resolver picks a provider from the per-simulation ``llm:`` config, then the
environment, then falls back to ``stub`` (precedence: config > env > stub).

Keys are read from the environment, never from committed YAML.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx

from .models import CompanyConfig


class LLMError(Exception):
    """Raised when an LLM call fails."""


@dataclass
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ProviderSpec:
    provider: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""


class LLMProvider(Protocol):
    name: str

    def generate(
        self, prompt: str, *, system: str = "", max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResult:
        ...


# --- default models / endpoints / key env vars per provider ----------------

_DEFAULT_MODEL = {
    "stub": "stub",
    "ollama": "llama3.1",
    "lmstudio": "local-model",
    "openai": "gpt-4o-mini",
    "openrouter": "anthropic/claude-3.5-sonnet",
    "gemini": "gemini-1.5-flash",
    "anthropic": "claude-sonnet-4-6",
}
_DEFAULT_BASE = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "ollama": "OLLAMA_API_KEY",
}

_TIMEOUT = httpx.Timeout(120.0)


# --- providers -------------------------------------------------------------

class StubProvider:
    """Deterministic, offline. Per-surface stub *content* lives in stubs.py;
    this generic fallback is only used if something calls generate() directly."""

    name = "stub"

    def generate(self, prompt: str, *, system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.7) -> LLMResult:
        return LLMResult(text="[stub output]", input_tokens=0, output_tokens=0)


class OpenAICompatibleProvider:
    """OpenAI-style /chat/completions — covers openai, openrouter, lmstudio."""

    def __init__(self, name: str, model: str, api_key: str, base_url: str):
        self.name = name
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt, *, system="", max_tokens=1024, temperature=0.7):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {"model": self.model, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature}
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body,
                           headers=headers, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"{self.name} request failed: {exc}") from exc
        usage = data.get("usage", {})
        return LLMResult(
            text=data["choices"][0]["message"]["content"],
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = (base_url or _DEFAULT_BASE["ollama"]).rstrip("/")

    def generate(self, prompt, *, system="", max_tokens=1024, temperature=0.7):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens}}
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=body,
                           headers=headers, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"ollama request failed: {exc}") from exc
        return LLMResult(
            text=data.get("message", {}).get("content", ""),
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
        )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    def generate(self, prompt, *, system="", max_tokens=1024, temperature=0.7):
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {"model": self.model, "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", json=body,
                           headers=headers, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"anthropic request failed: {exc}") from exc
        usage = data.get("usage", {})
        return LLMResult(
            text="".join(b.get("text", "") for b in data.get("content", [])),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    def generate(self, prompt, *, system="", max_tokens=1024, temperature=0.7):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature,
                                 "maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            r = httpx.post(url, json=body, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"gemini request failed: {exc}") from exc
        cand = (data.get("candidates") or [{}])[0]
        parts = cand.get("content", {}).get("parts", [])
        usage = data.get("usageMetadata", {})
        return LLMResult(
            text="".join(p.get("text", "") for p in parts),
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
        )


# --- resolution + construction --------------------------------------------

def resolve_spec(config: CompanyConfig | None = None) -> ProviderSpec:
    """Resolve the provider spec: config.llm > environment > stub."""
    provider = ""
    model = ""
    api_key = ""
    base_url = ""

    if config is not None and config.llm.provider:
        provider = config.llm.provider
        model = config.llm.model
        base_url = config.llm.base_url
        if config.llm.api_key_env:
            api_key = os.environ.get(config.llm.api_key_env, "")

    if not provider:
        provider = os.environ.get("LLM_PROVIDER", "stub")
        model = os.environ.get("LLM_MODEL", "")

    provider = provider.lower()
    if not model:
        model = _DEFAULT_MODEL.get(provider, "")
    if not base_url:
        base_url = _DEFAULT_BASE.get(provider, "")
    if not api_key and provider in _KEY_ENV:
        api_key = os.environ.get(_KEY_ENV[provider], "")

    return ProviderSpec(provider=provider, model=model, api_key=api_key, base_url=base_url)


def build_provider(spec: ProviderSpec) -> LLMProvider:
    p = spec.provider
    if p == "stub":
        return StubProvider()
    if p in ("openai", "openrouter", "lmstudio"):
        return OpenAICompatibleProvider(p, spec.model, spec.api_key, spec.base_url)
    if p == "ollama":
        return OllamaProvider(spec.model, spec.api_key, spec.base_url)
    if p == "anthropic":
        return AnthropicProvider(spec.model, spec.api_key)
    if p == "gemini":
        return GeminiProvider(spec.model, spec.api_key)
    raise LLMError(f"unknown LLM provider: {spec.provider!r}")


def get_provider(config: CompanyConfig | None = None) -> tuple[LLMProvider, ProviderSpec]:
    spec = resolve_spec(config)
    return build_provider(spec), spec
