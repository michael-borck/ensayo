"""AnythingLLM integration — workspace provisioning + embed widgets (spec §9).

A thin client over AnythingLLM's developer API. When no instance is configured
(no ``ANYTHINGLLM_URL`` / ``ANYTHINGLLM_API_KEY``), the client runs in **dry-run**
mode: it returns deterministic placeholder identifiers without any network calls,
so the provisioning flow is demonstrable and testable without a live instance.
Real calls are made when an instance is configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

_TIMEOUT = httpx.Timeout(60.0)


class AnythingLLMError(Exception):
    """Raised when an AnythingLLM API call fails."""


@dataclass
class WorkspaceResult:
    employee_slug: str
    workspace_slug: str
    embed_id: str
    status: str  # provisioned | dry-run | failed
    error: str = ""


class AnythingLLMClient:
    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @classmethod
    def from_env(cls) -> "AnythingLLMClient":
        return cls(os.environ.get("ANYTHINGLLM_URL", ""),
                   os.environ.get("ANYTHINGLLM_API_KEY", ""))

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    # URLs the generated site embeds (data-base-api-url + script src).
    def embed_base_url(self) -> str:
        return f"{self.base_url}/api/embed" if self.base_url else "about:dryrun"

    def embed_script_src(self) -> str:
        return (f"{self.base_url}/embed/anythingllm-chat.min.js"
                if self.base_url else "about:dryrun")

    def _post(self, path: str, json: dict) -> dict:
        try:
            r = httpx.post(f"{self.base_url}{path}",
                           headers={"Authorization": f"Bearer {self.api_key}",
                                    "Content-Type": "application/json"},
                           json=json, timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AnythingLLMError(f"POST {path} failed: {exc}") from exc

    # --- operations --------------------------------------------------------

    def create_workspace(self, name: str) -> str:
        data = self._post("/api/v1/workspace/new", {"name": name})
        slug = (data.get("workspace") or {}).get("slug")
        if not slug:
            raise AnythingLLMError(f"no workspace slug returned for {name!r}")
        return slug

    def set_system_prompt(self, workspace_slug: str, prompt: str) -> None:
        self._post(f"/api/v1/workspace/{workspace_slug}/update", {"openAiPrompt": prompt})

    def upload_text(self, title: str, content: str) -> str:
        data = self._post("/api/v1/document/raw-text",
                          {"textContent": content, "metadata": {"title": title}})
        docs = data.get("documents") or []
        if not docs or "location" not in docs[0]:
            raise AnythingLLMError(f"no document location returned for {title!r}")
        return docs[0]["location"]

    def embed_documents(self, workspace_slug: str, locations: list[str]) -> None:
        if locations:
            self._post(f"/api/v1/workspace/{workspace_slug}/update-embeddings",
                       {"adds": locations})

    def create_embed(self, workspace_slug: str) -> str:
        data = self._post("/api/v1/embed/new",
                          {"workspace_slug": workspace_slug, "enabled": True,
                           "chat_mode": "chat"})
        embed = data.get("embed") or data
        uuid = embed.get("uuid") or embed.get("id")
        if not uuid:
            raise AnythingLLMError(f"no embed uuid returned for {workspace_slug!r}")
        return str(uuid)
