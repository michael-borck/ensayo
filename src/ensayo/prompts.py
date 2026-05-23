"""Persona prompt + content builders.

Phase 0 ships a basic layered builder (company → individual). Phase 1 adds the
archetype and industry layers and a proper archetype library. Persona prompts
are written to ``content/employees/{slug}-prompt.txt`` in the repo and are the
canonical persona definition (spec §3.2, §15.1).
"""

from __future__ import annotations

import re

from .models import CompanyConfig, Employee


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_prompt(config: CompanyConfig, employee: Employee) -> str:
    """Assemble the chatbot system prompt for one employee."""
    company = config.company
    cust = employee.customisation
    parts: list[str] = []

    role = employee.role or "team member"
    parts.append(f"You are {employee.name}, {role} at {company.name}.")

    if company.profile.description:
        parts.append(company.profile.description.strip())

    if cust.background:
        parts.append("ABOUT YOU:\n" + cust.background.strip())

    personality = cust.personality_additions
    if personality:
        parts.append("PERSONALITY:\n" + _bullets(personality))

    knowledge = cust.knowledge_additions
    if knowledge:
        parts.append("WHAT YOU KNOW:\n" + _bullets(knowledge))

    if cust.opinions:
        parts.append("YOUR VIEWS:\n" + _bullets(cust.opinions))

    if cust.scenario_perspective:
        parts.append(
            "YOUR PERSPECTIVE ON THE CURRENT SITUATION:\n"
            + cust.scenario_perspective.strip()
        )

    if employee.refers_to:
        referrals = "\n".join(
            f"- For {topic}, refer them to {who}."
            for topic, who in employee.refers_to.items()
        )
        parts.append("WHEN A TOPIC ISN'T YOURS:\n" + referrals)

    parts.append(
        "Stay in character. Answer as this person would, drawing only on what "
        "they plausibly know. Keep replies conversational and concise. If asked "
        "something outside your role, say so and point them to the right colleague."
    )
    return "\n\n".join(parts).strip() + "\n"


def build_employee_markdown(config: CompanyConfig, employee: Employee) -> str:
    """Build the ``{slug}.md`` profile file (YAML frontmatter + backstory)."""
    cust = employee.customisation
    fm: list[str] = ["---"]
    fm.append(f"name: {_yaml_str(employee.name)}")
    fm.append(f"slug: {employee.slug}")
    fm.append(f"role: {_yaml_str(employee.role)}")
    fm.append(f"tier: {employee.tier.value}")
    if employee.department:
        fm.append(f"department: {_yaml_str(employee.department)}")
    if cust.personality_additions:
        fm.append("personality:")
        fm += [f"  - {_yaml_str(p)}" for p in cust.personality_additions]
    if cust.knowledge_additions:
        fm.append("knowledge:")
        fm += [f"  - {_yaml_str(k)}" for k in cust.knowledge_additions]
    if employee.refers_to:
        fm.append("refers_to:")
        fm += [f"  {topic}: {_yaml_str(who)}" for topic, who in employee.refers_to.items()]
    fm.append("---")

    body = [f"# {employee.name} — {employee.role}".rstrip(" —")]
    if cust.background:
        body.append(cust.background.strip())
    if cust.scenario_perspective:
        body.append("## On the current situation\n\n" + cust.scenario_perspective.strip())
    return "\n".join(fm) + "\n\n" + "\n\n".join(body) + "\n"


def build_keyword_responses(config: CompanyConfig, employee: Employee) -> dict:
    """Produce a basic keyword-chatbot dataset for an employee.

    Phase 0 derives a small response map from the persona so the zero-config demo
    has a working (deterministic) chatbot with no LLM. Phase 1 makes this a
    first-class authored ``keywords.json``.
    """
    cust = employee.customisation
    rules: list[dict] = []

    if cust.background:
        rules.append({
            "keywords": ["who are you", "your role", "what do you do", "your job"],
            "response": _first_sentences(cust.background, 2),
        })
    for opinion in cust.opinions[:4]:
        topic = _topic_keywords(opinion)
        if topic:
            rules.append({"keywords": topic, "response": opinion})
    for area in cust.knowledge_additions[:6]:
        rules.append({
            "keywords": _topic_keywords(area),
            "response": f"That's something I work with a lot — {area.lower()}. Ask me anything specific.",
        })
    for topic, who in employee.refers_to.items():
        rules.append({
            "keywords": [topic],
            "response": f"For {topic}, you really want to talk to {who}.",
        })

    greeting = f"Hi, I'm {employee.name}"
    if employee.role:
        greeting += f", {employee.role}"
    greeting += f" at {config.company.name}. What would you like to know?"

    return {
        "employee": employee.name,
        "role": employee.role,
        "greeting": greeting,
        "fallback": "I'm not sure about that one — try asking me about my work, or ask a colleague.",
        "rules": rules,
    }


# --- helpers ---------------------------------------------------------------

def _yaml_str(value: str) -> str:
    if value and re.search(r"[:#\[\]{}&*!|>'\"%@`]", value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def _first_sentences(text: str, count: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return " ".join(sentences[:count]).strip()


_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with",
    "our", "we", "you", "your", "their", "they", "is", "are", "be", "more",
    "than", "that", "this", "it", "i", "my", "me", "at", "as", "by", "from",
}


def _topic_keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]+", text.lower())
    keywords = [w for w in words if len(w) > 3 and w not in _STOPWORDS]
    return keywords[:3]
