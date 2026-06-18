"""Tests for worldoracle CLI using Click's CliRunner."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from worldoracle.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Return a Click test runner."""
    return CliRunner()


@pytest.fixture
def cli_db(tmp_path: pytest.TempPathFactory) -> str:
    """Return a temp database path for CLI tests."""
    return str(tmp_path / "cli-test.db")


def test_help_returns_zero(runner: CliRunner) -> None:
    """worldoracle --help should exit 0."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "NPC contradiction" in result.output


def test_add_subcommand_help(runner: CliRunner) -> None:
    """worldoracle add --help should exit 0."""
    result = runner.invoke(main, ["add", "--help"])
    assert result.exit_code == 0


def test_add_predicate(runner: CliRunner, cli_db: str) -> None:
    """worldoracle add should store a predicate and exit 0."""
    result = runner.invoke(main, ["--db", cli_db, "add", "guard-1", "king", "alive", "True"])
    assert result.exit_code == 0
    assert "Added predicate" in result.output


def test_check_no_contradictions(runner: CliRunner, cli_db: str) -> None:
    """worldoracle check on a consistent NPC should report no contradictions."""
    runner.invoke(main, ["--db", cli_db, "add", "guard-1", "king", "alive", "True"])
    result = runner.invoke(main, ["--db", cli_db, "check", "guard-1"])
    assert result.exit_code == 0
    assert "No contradictions" in result.output


def test_add_then_check_finds_contradiction(runner: CliRunner, cli_db: str) -> None:
    """Adding two conflicting predicates then check should report contradiction."""
    runner.invoke(main, ["--db", cli_db, "add", "guard-1", "king", "alive", "True"])
    runner.invoke(main, ["--db", cli_db, "add", "guard-1", "king", "alive", "False"])
    result = runner.invoke(main, ["--db", cli_db, "check", "guard-1"])
    assert result.exit_code == 0
    assert "contradiction" in result.output.lower()


def test_repair_on_contradicting_npc(runner: CliRunner, cli_db: str) -> None:
    """worldoracle repair should generate repair frames for contradictions."""
    runner.invoke(main, [
        "--db", cli_db, "add", "guard-1", "king", "alive", "True", "--confidence", "0.5",
    ])
    runner.invoke(main, [
        "--db", cli_db, "add", "guard-1", "king", "alive", "False", "--confidence", "0.9",
    ])
    result = runner.invoke(main, ["--db", cli_db, "repair", "guard-1"])
    assert result.exit_code == 0


def test_beliefs_lists_predicates(runner: CliRunner, cli_db: str) -> None:
    """worldoracle beliefs should list the NPC's predicates."""
    runner.invoke(main, ["--db", cli_db, "add", "guard-1", "king", "alive", "True"])
    result = runner.invoke(main, ["--db", cli_db, "beliefs", "guard-1"])
    assert result.exit_code == 0


def test_status_shows_npc_count(runner: CliRunner, cli_db: str) -> None:
    """worldoracle status should list NPCs."""
    runner.invoke(main, ["--db", cli_db, "add", "guard-1", "king", "alive", "True"])
    runner.invoke(main, ["--db", cli_db, "add", "guard-2", "queen", "alive", "True"])
    result = runner.invoke(main, ["--db", cli_db, "status"])
    assert result.exit_code == 0
    assert "NPCs tracked: 2" in result.output


def test_check_on_empty_npc(runner: CliRunner, cli_db: str) -> None:
    """worldoracle check on unknown NPC should report no contradictions."""
    result = runner.invoke(main, ["--db", cli_db, "check", "unknown-npc"])
    assert result.exit_code == 0
    assert "No contradictions" in result.output
