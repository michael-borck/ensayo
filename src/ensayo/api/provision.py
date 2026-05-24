"""Provision AnythingLLM chatbot workspaces for a simulation's employees (spec §9.2).

For each employee: create a workspace, set its system prompt from the canonical
persona ``.txt``, upload the simulation's documents for RAG, and create an embed
widget. The resulting embed ids + connection details are written back into the
simulation's ``company.yaml`` and the site is regenerated so the embeds render.

Runs in dry-run mode (placeholder ids, no network) when no AnythingLLM instance
is configured, so the flow works end to end without a live instance.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ..config import dump_config_yaml, load_company_config
from ..models import ChatbotMode
from .anythingllm import AnythingLLMClient, AnythingLLMError, WorkspaceResult
from .service import ServiceError, regenerate, simulation_lock

Logger = "callable"


def provision_chatbots(conn: sqlite3.Connection, sim: sqlite3.Row, *,
                       build: bool = True, log=lambda m: None) -> dict:
    if sim["audience"] == "minors":
        raise ServiceError("LLM chatbots are disabled for minors-audience simulations")

    clone = Path(sim["working_clone_path"])
    cfg_path = clone / "company.yaml"
    if not cfg_path.exists():
        raise ServiceError(f"working clone missing company.yaml: {clone}")
    config = load_company_config(cfg_path)
    client = AnythingLLMClient.from_env()
    mode = "configured" if client.configured else "dry-run"
    log(f"AnythingLLM provisioning ({mode}) for {config.slug}")

    # Upload shared RAG documents once (real mode only).
    doc_locations: list[str] = []
    if client.configured:
        for doc in config.documents:
            try:
                doc_locations.append(
                    client.upload_text(doc.title, doc.content or doc.brief or doc.title))
            except AnythingLLMError as exc:
                log(f"  doc upload failed ({doc.title}): {exc}")

    results: list[WorkspaceResult] = []
    for emp in config.employees:
        ws_name = f"{config.slug}_{emp.slug}"
        prompt_file = clone / "content" / "employees" / f"{emp.slug}-prompt.txt"
        prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""

        if not client.configured:
            res = WorkspaceResult(emp.slug, ws_name, f"dryrun-{ws_name}", "dry-run")
        else:
            try:
                ws = client.create_workspace(ws_name)
                if prompt:
                    client.set_system_prompt(ws, prompt)
                client.embed_documents(ws, doc_locations)
                res = WorkspaceResult(emp.slug, ws, client.create_embed(ws), "provisioned")
            except AnythingLLMError as exc:
                results.append(WorkspaceResult(emp.slug, ws_name, "", "failed", str(exc)))
                log(f"  {emp.name}: failed — {exc}")
                continue

        emp.chatbot_embed_id = res.embed_id
        emp.chatbot_mode = ChatbotMode.llm
        results.append(res)
        log(f"  {emp.name}: {res.status} (embed {res.embed_id})")

    # Connection details the generated pages embed.
    config.anythingllm.base_url = client.embed_base_url()
    config.anythingllm.embed_src = client.embed_script_src()

    # Persist YAML, then regenerate so the embeds appear in the built site.
    with simulation_lock(sim["slug"]):
        cfg_path.write_text(dump_config_yaml(config), encoding="utf-8")
    regenerate(conn, sim, build=build, log=log)
    conn.execute(
        "UPDATE simulations SET config_cache = ?, has_unpublished_changes = 1, "
        "updated_at = ? WHERE id = ?",
        (json.dumps(config.model_dump(mode="json")),
         datetime.now(timezone.utc).isoformat(), sim["id"]))
    conn.commit()

    provisioned = sum(1 for r in results if r.status in ("provisioned", "dry-run"))
    return {"mode": mode, "provisioned": provisioned,
            "failed": sum(1 for r in results if r.status == "failed"),
            "results": [asdict(r) for r in results]}
