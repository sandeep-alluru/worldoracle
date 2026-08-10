"""COLLECTIVE-CERT — multi-agent consensus certificates (arXiv 2608.05956)."""

from __future__ import annotations

import pytest

from worldoracle.closed_loop import ClosedLoopError
from worldoracle.collective import (
    AgentVote,
    assert_collective_consensus_ok,
    certify_consensus,
    estimate_deadline,
    gate_collective_consensus,
)


def test_empty_fails_loud() -> None:
    out = gate_collective_consensus([], decision="finalize")
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert "COLLECTIVE-CERT" in out.reason


def test_single_agent_fails_loud() -> None:
    out = gate_collective_consensus(
        [AgentVote("a1", "yes", 0)],
        decision="finalize",
        min_agents=2,
    )
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"


def test_finalize_without_agreement_fails() -> None:
    votes = [
        AgentVote("a", "yes", 0),
        AgentVote("b", "no", 0),
        AgentVote("c", "maybe", 0),
    ]
    out = gate_collective_consensus(votes, decision="finalize", min_agreement=0.67)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "not converged" in out.reason.lower() or "finalize" in out.reason


def test_finalize_when_agreed_passes() -> None:
    votes = [
        AgentVote("a", "yes", 1),
        AgentVote("b", "yes", 1),
        AgentVote("c", "yes", 1),
    ]
    out = gate_collective_consensus(votes, decision="finalize", min_agreement=0.67)
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.consistency_score == 1.0


def test_continue_when_converged_fails() -> None:
    votes = [AgentVote("a", "x", 0), AgentVote("b", "x", 0)]
    out = gate_collective_consensus(votes, decision="continue")
    assert out.ok is False
    assert "already converged" in out.reason.lower() or "continue" in out.reason


def test_continue_while_debating_passes() -> None:
    votes = [
        AgentVote("a", "yes", 0),
        AgentVote("b", "no", 0),
        AgentVote("c", "yes", 0),
    ]
    # 2/3 agreement may still fail min if max_factions=1 — set max_factions high
    out = gate_collective_consensus(
        votes,
        decision="continue",
        min_agreement=0.9,
        max_factions=1,
    )
    assert out.ok is True
    assert out.verdict == "PASS"


def test_certify_factions() -> None:
    cert = certify_consensus(
        [
            {"agent_id": "1", "choice": "A", "round": 0},
            {"agent_id": "2", "choice": "B", "round": 0},
            {"agent_id": "1", "choice": "A", "round": 1},
            {"agent_id": "2", "choice": "A", "round": 1},
        ],
        min_agreement=0.99,
        max_factions=1,
    )
    assert cert.n_agents == 2
    assert cert.n_rounds == 2
    assert cert.agreement == 1.0
    assert cert.plurality_choice == "A"
    assert cert.lambda2_hat == 0.0
    assert cert.converged is True
    assert cert.to_dict()["vote_count"] == 4


def test_estimate_deadline() -> None:
    assert estimate_deadline(0.0) == 0
    assert estimate_deadline(1.0) is None
    d = estimate_deadline(0.5, residual=0.05)
    assert d is not None
    assert d > 0


def test_stuck_rounds_fails() -> None:
    votes = []
    for r in range(10):
        votes.append(AgentVote("a", "yes", r))
        votes.append(AgentVote("b", "no", r))
    out = gate_collective_consensus(
        votes,
        decision="continue",
        min_agreement=0.9,
        max_rounds_without_convergence=5,
    )
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.human_required is True


def test_assert_raises() -> None:
    with pytest.raises(ClosedLoopError):
        assert_collective_consensus_ok([], decision="finalize")


def test_arxiv_collective_fixture() -> None:
    """End-to-end: black-box finalize refused; certified agreement accepted."""
    # Pre-fix: agents still split after several rounds
    split = [
        AgentVote("alpha", "approve", 3),
        AgentVote("beta", "reject", 3),
        AgentVote("gamma", "approve", 3),
        AgentVote("delta", "reject", 3),
    ]
    refuse = gate_collective_consensus(
        split, decision="finalize", min_agreement=0.75, max_factions=1
    )
    assert refuse.ok is False
    assert refuse.verdict == "FAIL"
    assert "2608.05956" in refuse.reason or "COLLECTIVE" in refuse.reason

    # Post-fix: converged vote
    done = [
        AgentVote("alpha", "approve", 5),
        AgentVote("beta", "approve", 5),
        AgentVote("gamma", "approve", 5),
        AgentVote("delta", "approve", 5),
    ]
    ok = gate_collective_consensus(done, decision="finalize")
    assert ok.ok is True
    cert = certify_consensus(done)
    assert cert.converged is True
    assert cert.lambda2_hat == 0.0
