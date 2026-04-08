"""Basic CLI tests."""

from click.testing import CliRunner

from ensayo.cli import main


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "ensayo" in result.output


def test_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "simulation" in result.output.lower()


def test_build_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["build", "--help"])
    assert result.exit_code == 0
    assert "--config" in result.output


def test_content_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["content", "--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
