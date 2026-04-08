"""Tests for booking config export."""

from pathlib import Path

from ensayo.booking import export_booking_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_export_booking_config() -> None:
    config = export_booking_config(
        FIXTURES / "content",
        site_config_path=FIXTURES / "site.yaml",
    )
    assert config["simulation"]["name"] == "Test Company"
    assert len(config["employees"]) == 1

    emp = config["employees"][0]
    assert emp["name"] == "Jane Doe"
    assert emp["role"] == "Managing Director"
    assert emp["tier"] == "executive"
    assert emp["slots_per_day"] == 2
    assert emp["slot_duration_minutes"] == 20
    assert emp["enabled"] is True


def test_export_booking_config_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "employees.json"
    export_booking_config(
        FIXTURES / "content",
        site_config_path=FIXTURES / "site.yaml",
        output_path=output,
    )
    assert output.is_file()

    import json

    data = json.loads(output.read_text())
    assert len(data["employees"]) == 1
    assert "defaults" in data


def test_export_booking_config_no_site_yaml() -> None:
    config = export_booking_config(FIXTURES / "content")
    assert config["simulation"]["name"] == "Simulation"
    assert len(config["employees"]) == 1


def test_export_booking_slug_to_id() -> None:
    config = export_booking_config(FIXTURES / "content")
    emp = config["employees"][0]
    # slug "jane-doe" should become "jane_doe"
    assert emp["id"] == "jane_doe"
