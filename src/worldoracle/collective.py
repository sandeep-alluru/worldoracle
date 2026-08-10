"""COLLECTIVE-CERT — multi-agent consensus certificates (arXiv 2608.05956).

Public case: *Certifying Collective Reasoning in Multi-Agent Systems via
Koopman Spectral Analysis*. Multi-agent debate/vote collectives are black
boxes: no principled convergence test, no bound on rounds, no account of
what drove the decision. The paper extracts machine-checkable certificates
from interaction dynamics (λ₂ timescale, faction eigenvectors, spectral
coordinates).

Product role in worldoracle (belief twin of LEGAL-NO-AUTOFIX):
  Gate **finalize** of multi-agent belief votes with a load-bearing certificate:
  agreement rate, faction split, estimated mixing timescale, and a deadline
  before which finalize is refused.

This is a **gate-facing** certificate over vote traces — not a full Koopman
operator estimator. Integrators can plug formal λ₂ later; the refuse paths
are the product.

Non-Ornament:
  Call ``gate_collective_consensus`` before accepting a multi-agent decision.
  Pair with ``gate_beliefs`` for single-world contradictions.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from worldoracle.closed_loop import ClosedLoopError, GateOutcome

Decision = Literal["continue", "finalize"]


@dataclass(frozen=True)
class AgentVote:
    """One agent vote in a debate/consensus round."""

    agent_id: str
    choice: str
    round: int = 0
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "choice": self.choice,
            "round": self.round,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ConsensusCertificate:
    """Machine-checkable snapshot of collective agreement.

    Attributes:
        n_agents: Distinct agents seen.
        n_rounds: Max round index + 1.
        agreement: Fraction agreeing with plurality choice (latest round).
        plurality_choice: Mode of latest-round votes.
        faction_count: Number of distinct choices in latest round.
        factions: choice → agent_ids (latest round).
        lambda2_hat: Proxy for sub-dominant mixing: 1 - agreement
            (0 = fully mixed/agreed, closer to 1 = slow/stuck factions).
        deadline_rounds: Estimated rounds to agreement under geometric
            contraction (ceil log residual / log lambda2) when lambda2 < 1.
        converged: agreement >= min_agreement and faction_count <= max_factions.
    """

    n_agents: int
    n_rounds: int
    agreement: float
    plurality_choice: str
    faction_count: int
    factions: dict[str, tuple[str, ...]]
    lambda2_hat: float
    deadline_rounds: int | None
    converged: bool
    vote_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_agents": self.n_agents,
            "n_rounds": self.n_rounds,
            "agreement": self.agreement,
            "plurality_choice": self.plurality_choice,
            "faction_count": self.faction_count,
            "factions": {k: list(v) for k, v in self.factions.items()},
            "lambda2_hat": self.lambda2_hat,
            "deadline_rounds": self.deadline_rounds,
            "converged": self.converged,
            "vote_count": self.vote_count,
        }


def _as_vote(item: AgentVote | dict[str, Any], index: int = 0) -> AgentVote:
    if isinstance(item, AgentVote):
        return item
    if not isinstance(item, dict):
        raise TypeError(f"vote must be AgentVote or dict, got {type(item)!r}")
    aid = str(item.get("agent_id") or item.get("agent") or item.get("id") or f"a{index}")
    choice = str(item.get("choice") or item.get("vote") or item.get("value") or "").strip()
    if not choice:
        raise ValueError(f"vote for {aid!r} missing choice")
    raw_round = item.get("round", item.get("t", 0))
    return AgentVote(
        agent_id=aid,
        choice=choice,
        round=int(raw_round if raw_round is not None else 0),
        confidence=float(item.get("confidence", 1.0) or 0.0),
    )


def _latest_round_votes(votes: Sequence[AgentVote]) -> list[AgentVote]:
    if not votes:
        return []
    # latest vote per agent by max round
    best: dict[str, AgentVote] = {}
    for v in votes:
        prev = best.get(v.agent_id)
        if prev is None or v.round >= prev.round:
            best[v.agent_id] = v
    return list(best.values())


def estimate_deadline(
    lambda2_hat: float, *, residual: float = 0.05, max_rounds: int = 10_000
) -> int | None:
    """Estimate rounds until residual disagreement under geometric contraction.

    deadline ≈ ceil( ln(residual) / ln(λ₂) ) when 0 < λ₂ < 1.
    Returns 0 if already mixed (λ₂≈0), None if λ₂ >= 1 (no contraction).
    """
    import math

    if lambda2_hat <= 1e-12:
        return 0
    if lambda2_hat >= 1.0 - 1e-12:
        return None
    if residual <= 0 or residual >= 1:
        residual = 0.05
    # ln(residual) / ln(lambda2) both negative for residual,lambda2 in (0,1)
    val = math.log(residual) / math.log(lambda2_hat)
    if val < 0:
        return None
    return min(max_rounds, max(0, math.ceil(val)))


def certify_consensus(
    votes: Sequence[AgentVote | dict[str, Any]],
    *,
    min_agreement: float = 0.67,
    max_factions: int = 1,
) -> ConsensusCertificate:
    """Build a consensus certificate from multi-agent vote traces."""
    parsed = [_as_vote(v, i) for i, v in enumerate(votes)]
    if not parsed:
        return ConsensusCertificate(
            n_agents=0,
            n_rounds=0,
            agreement=0.0,
            plurality_choice="",
            faction_count=0,
            factions={},
            lambda2_hat=1.0,
            deadline_rounds=None,
            converged=False,
            vote_count=0,
        )

    latest = _latest_round_votes(parsed)
    n_agents = len(latest)
    n_rounds = max(v.round for v in parsed) + 1
    counts = Counter(v.choice for v in latest)
    plurality_choice, top_n = counts.most_common(1)[0]
    agreement = top_n / n_agents if n_agents else 0.0
    factions: dict[str, tuple[str, ...]] = defaultdict(tuple)
    by_choice: dict[str, list[str]] = defaultdict(list)
    for v in latest:
        by_choice[v.choice].append(v.agent_id)
    factions = {c: tuple(sorted(aids)) for c, aids in by_choice.items()}
    faction_count = len(factions)

    # λ₂ proxy: disagreement mass (paper: sub-dominant mode scales slow mixing)
    lambda2_hat = max(0.0, min(1.0, 1.0 - agreement))
    deadline = estimate_deadline(lambda2_hat)
    converged = agreement >= min_agreement and faction_count <= max_factions

    return ConsensusCertificate(
        n_agents=n_agents,
        n_rounds=n_rounds,
        agreement=agreement,
        plurality_choice=plurality_choice,
        faction_count=faction_count,
        factions=factions,
        lambda2_hat=lambda2_hat,
        deadline_rounds=deadline,
        converged=converged,
        vote_count=len(parsed),
    )


def gate_collective_consensus(
    votes: Sequence[AgentVote | dict[str, Any]] | None,
    *,
    decision: Decision = "finalize",
    min_agreement: float = 0.67,
    max_factions: int = 1,
    min_agents: int = 2,
    max_rounds_without_convergence: int | None = None,
    require_votes: bool = True,
) -> GateOutcome:
    """Refuse uncertified multi-agent finalize (COLLECTIVE-CERT / arXiv 2608.05956).

    Rules:

    * No votes when required → **FAIL_LOUD**
    * Fewer than ``min_agents`` → **FAIL_LOUD**
    * ``decision=finalize`` without convergence → **FAIL** (black-box stop)
    * ``decision=finalize`` past deadline without agreement → **FAIL**
    * ``decision=continue`` when already converged → **FAIL** (waste rounds)
    * ``decision=continue`` while not converged (under round budget) → **PASS**
    * ``decision=finalize`` when converged → **PASS** + certificate fields
    """
    dec = (decision or "").strip().lower()
    if dec not in {"continue", "finalize"}:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=f"COLLECTIVE-CERT: unknown decision={decision!r} (use continue|finalize)",
            exit_code=2,
            human_required=True,
        )

    if not votes:
        if require_votes:
            return GateOutcome(
                ok=False,
                verdict="FAIL_LOUD",
                reason=(
                    "COLLECTIVE-CERT: no agent votes — refuse consensus certificate "
                    "before interaction traces exist (arXiv 2608.05956 black-box class)"
                ),
                exit_code=2,
                human_required=True,
            )
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason="COLLECTIVE-CERT: no votes required",
            exit_code=0,
        )

    try:
        cert = certify_consensus(votes, min_agreement=min_agreement, max_factions=max_factions)
    except (TypeError, ValueError) as exc:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=f"COLLECTIVE-CERT: invalid vote payload: {exc}",
            exit_code=2,
            human_required=True,
        )

    if cert.n_agents < min_agents:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=(
                f"COLLECTIVE-CERT: n_agents={cert.n_agents} < min_agents={min_agents} "
                "— collective certificate needs multi-agent interaction"
            ),
            exit_code=2,
            human_required=True,
            contradictions_found=cert.faction_count,
            consistency_score=cert.agreement,
        )

    if (
        max_rounds_without_convergence is not None
        and not cert.converged
        and cert.n_rounds > max_rounds_without_convergence
        and dec == "continue"
    ):
        return GateOutcome(
            ok=False,
            verdict="FAIL",
            reason=(
                f"COLLECTIVE-CERT: n_rounds={cert.n_rounds} exceeds "
                f"max_rounds_without_convergence={max_rounds_without_convergence} "
                f"with agreement={cert.agreement:.3f} λ2_hat={cert.lambda2_hat:.3f} "
                f"factions={cert.faction_count} — stuck collective; escalate"
            ),
            exit_code=1,
            human_required=True,
            consistency_score=cert.agreement,
            contradictions_found=cert.faction_count,
        )

    if dec == "finalize" and not cert.converged:
        return GateOutcome(
            ok=False,
            verdict="FAIL",
            reason=(
                f"COLLECTIVE-CERT: decision=finalize but not converged "
                f"agreement={cert.agreement:.3f} (min={min_agreement}) "
                f"factions={cert.faction_count} (max={max_factions}) "
                f"λ2_hat={cert.lambda2_hat:.3f} deadline_rounds={cert.deadline_rounds} "
                f"plurality={cert.plurality_choice!r} — refuse black-box stop "
                f"(arXiv 2608.05956)"
            ),
            exit_code=1,
            human_required=True,
            consistency_score=cert.agreement,
            contradictions_found=cert.faction_count,
        )

    if dec == "continue" and cert.converged:
        return GateOutcome(
            ok=False,
            verdict="FAIL",
            reason=(
                f"COLLECTIVE-CERT: decision=continue but already converged "
                f"agreement={cert.agreement:.3f} choice={cert.plurality_choice!r} "
                f"— refuse extra debate rounds after certificate (waste)"
            ),
            exit_code=1,
            human_required=False,
            consistency_score=cert.agreement,
            contradictions_found=0,
        )

    if dec == "finalize":
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason=(
                f"COLLECTIVE-CERT ok: finalize choice={cert.plurality_choice!r} "
                f"agreement={cert.agreement:.3f} agents={cert.n_agents} "
                f"rounds={cert.n_rounds} λ2_hat={cert.lambda2_hat:.3f}"
            ),
            exit_code=0,
            human_required=False,
            consistency_score=cert.agreement,
            contradictions_found=0,
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"COLLECTIVE-CERT ok: continue agreement={cert.agreement:.3f} "
            f"factions={cert.faction_count} λ2_hat={cert.lambda2_hat:.3f} "
            f"deadline_rounds={cert.deadline_rounds}"
        ),
        exit_code=0,
        human_required=False,
        consistency_score=cert.agreement,
        contradictions_found=cert.faction_count,
    )


def assert_collective_consensus_ok(
    votes: Sequence[AgentVote | dict[str, Any]] | None,
    **kwargs: Any,
) -> GateOutcome:
    """Raise :class:`ClosedLoopError` unless :func:`gate_collective_consensus` is ok."""
    outcome = gate_collective_consensus(votes, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome
