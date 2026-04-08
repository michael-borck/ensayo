"""Export employee configuration for the sim-booking-api."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from ensayo.content import load_employees, load_site_config
from ensayo.models import Employee

console = Console()

# Default booking slot configuration per tier
TIER_DEFAULTS: dict[str, dict[str, Any]] = {
    "executive": {
        "slots_per_day": 2,
        "slot_duration_minutes": 20,
        "reschedule_probability": 0.25,
        "busy_message": "I have a very full schedule. Please try another time.",
    },
    "manager": {
        "slots_per_day": 4,
        "slot_duration_minutes": 30,
        "reschedule_probability": 0.10,
        "busy_message": "I'm in meetings most of the day. Check back tomorrow.",
    },
    "specialist": {
        "slots_per_day": 5,
        "slot_duration_minutes": 30,
        "reschedule_probability": 0.08,
        "busy_message": "I'm out on a job right now. Try again later.",
    },
}


def _employee_to_booking(emp: Employee) -> dict[str, Any]:
    """Convert an Employee to a booking API employee config entry."""
    tier_config = TIER_DEFAULTS.get(emp.tier, TIER_DEFAULTS["specialist"])
    return {
        "id": emp.slug.replace("-", "_"),
        "name": emp.name,
        "role": emp.role,
        "tier": emp.tier,
        "enabled": True,
        **tier_config,
    }


def export_booking_config(
    content_dir: Path,
    site_config_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate a booking API employees.json from content.

    Returns the config dict. If output_path is given, also writes to file.
    """
    employees = load_employees(content_dir)

    # Build simulation metadata
    simulation: dict[str, Any] = {"name": "Simulation", "description": ""}
    if site_config_path and site_config_path.is_file():
        config = load_site_config(site_config_path)
        simulation = {
            "name": config.company.name,
            "description": config.company.tagline,
        }

    config_data: dict[str, Any] = {
        "simulation": simulation,
        "defaults": {
            "available_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "business_hours": {"start": "07:00", "end": "19:00"},
        },
        "employees": [_employee_to_booking(emp) for emp in employees],
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        console.print(
            f"[green]Exported {len(employees)} employees → {output_path}[/green]"
        )

    return config_data
