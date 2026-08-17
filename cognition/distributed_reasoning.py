"""
DistributedReasoning — multi-node consensus reasoning via Redis Pub/Sub.

Protocol:
  1. Proposer node broadcasts a ReasoningProposal to all nodes
  2. Each participant node runs local reasoning and broadcasts a ReasoningVote
  3. Proposer waits up to _VOTE_TIMEOUT_S for votes
  4. Proposer aggregates votes (weighted by confidence) → CognitionState
  5. Final CognitionState broadcast to all nodes

Consensus threshold: 60% agreement by weighted confidence
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import redis.asyncio as aioredis

from edge.types import CognitionState

logger = logging.getLogger(__name__)

_PROPOSAL_CHANNEL = "argus:cognition:proposals"
_VOTE_CHANNEL_TEMPLATE = "argus:cognition:votes:{proposal_id}"
_RESULT_CHANNEL = "argus:cognition:results"
_VOTE_TIMEOUT_S = 10.0
_CONSENSUS_THRESHOLD = 0.60
_MAX_PARTICIPANTS = 20


@dataclass
class ReasoningProposal:
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    proposer_node: str = ""
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    question: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "proposal_id": self.proposal_id,
            "session_id": self.session_id,
            "proposer_node": self.proposer_node,
            "context_snapshot": self.context_snapshot,
            "question": self.question,
            "timestamp": self.timestamp,
        })

    @classmethod
    def from_json(cls, raw: str) -> "ReasoningProposal":
        data = json.loads(raw)
        return cls(**{k: data[k] for k in ("proposal_id", "session_id", "proposer_node",
                                            "context_snapshot", "question", "timestamp")
                      if k in data})


@dataclass
class ReasoningVote:
    proposal_id: str
    voter_node: str
    insight: dict[str, Any]     # serialized AIInsight or simplified
    confidence: float
    agree: bool
    reasoning: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "proposal_id": self.proposal_id,
            "voter_node": self.voter_node,
            "insight": self.insight,
            "confidence": self.confidence,
            "agree": self.agree,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        })

    @classmethod
    def from_json(cls, raw: str) -> "ReasoningVote":
        data = json.loads(raw)
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


# Type alias for a local reasoning function
LocalReasonerFn = Callable[[ReasoningProposal], Coroutine[Any, Any, ReasoningVote]]


class DistributedReasoning:
    """
    Coordinates multi-node consensus reasoning.

    Each node creates one instance.  The proposer calls propose();
    participant nodes handle incoming proposals via _listen_loop().
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        node_id: str,
        local_reasoner: LocalReasonerFn | None = None,
    ) -> None:
        self._redis = redis_client
        self._node_id = node_id
        self._local_reasoner = local_reasoner
        self._running = False
        self._listener_task: asyncio.Task | None = None
        self._proposals_handled = 0
        self._consensus_reached = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._listener_task = asyncio.create_task(
            self._listen_loop(), name="distributed_reasoning_listener"
        )
        logger.info("distributed_reasoning started node=%s", self._node_id)

    async def stop(self) -> None:
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Propose (called by proposer node)
    # ------------------------------------------------------------------

    async def propose(
        self,
        session_id: str,
        context_snapshot: dict[str, Any],
        question: str = "What is the current safety assessment?",
        *,
        vote_timeout_s: float = _VOTE_TIMEOUT_S,
    ) -> CognitionState:
        proposal = ReasoningProposal(
            session_id=session_id,
            proposer_node=self._node_id,
            context_snapshot=context_snapshot,
            question=question,
        )

        vote_channel = _VOTE_CHANNEL_TEMPLATE.format(proposal_id=proposal.proposal_id)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(vote_channel)

        try:
            await self._redis.publish(_PROPOSAL_CHANNEL, proposal.to_json())
            votes = await self._collect_votes(pubsub, proposal.proposal_id, vote_timeout_s)
        finally:
            await pubsub.unsubscribe(vote_channel)

        cognition_state = self._aggregate_votes(proposal, votes)

        # Broadcast result
        await self._redis.publish(_RESULT_CHANNEL, json.dumps(cognition_state.to_dict()))
        self._consensus_reached += 1
        logger.info(
            "distributed_reasoning consensus session=%s agreement=%.2f participants=%d",
            session_id, cognition_state.agreement_score, len(cognition_state.participating_nodes),
        )
        return cognition_state

    # ------------------------------------------------------------------
    # Participant listener (all non-proposer nodes)
    # ------------------------------------------------------------------

    async def _listen_loop(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_PROPOSAL_CHANNEL)
        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                if message["type"] != "message":
                    continue
                try:
                    proposal = ReasoningProposal.from_json(message["data"])
                    if proposal.proposer_node == self._node_id:
                        continue  # don't vote on own proposals
                    await self._handle_proposal(proposal)
                except Exception as exc:
                    logger.debug("distributed_reasoning proposal_parse_error: %s", exc)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(_PROPOSAL_CHANNEL)

    async def _handle_proposal(self, proposal: ReasoningProposal) -> None:
        self._proposals_handled += 1
        if self._local_reasoner is None:
            return

        try:
            vote = await asyncio.wait_for(
                self._local_reasoner(proposal), timeout=_VOTE_TIMEOUT_S * 0.8
            )
        except asyncio.TimeoutError:
            logger.warning("distributed_reasoning local_reasoner_timeout proposal=%s", proposal.proposal_id)
            return
        except Exception as exc:
            logger.error("distributed_reasoning local_reasoner_error: %s", exc)
            return

        vote_channel = _VOTE_CHANNEL_TEMPLATE.format(proposal_id=proposal.proposal_id)
        try:
            await self._redis.publish(vote_channel, vote.to_json())
        except Exception as exc:
            logger.debug("distributed_reasoning vote_publish_error: %s", exc)

    # ------------------------------------------------------------------
    # Vote collection + aggregation
    # ------------------------------------------------------------------

    async def _collect_votes(
        self,
        pubsub: Any,
        proposal_id: str,
        timeout_s: float,
    ) -> list[ReasoningVote]:
        votes: list[ReasoningVote] = []
        deadline = time.monotonic() + timeout_s
        try:
            async for message in pubsub.listen():
                if time.monotonic() > deadline:
                    break
                if message["type"] != "message":
                    continue
                try:
                    vote = ReasoningVote.from_json(message["data"])
                    if vote.proposal_id == proposal_id:
                        votes.append(vote)
                        if len(votes) >= _MAX_PARTICIPANTS:
                            break
                except Exception:
                    pass
        except asyncio.TimeoutError:
            pass
        return votes

    def _aggregate_votes(
        self,
        proposal: ReasoningProposal,
        votes: list[ReasoningVote],
    ) -> CognitionState:
        if not votes:
            return CognitionState(
                session_id=proposal.session_id,
                participating_nodes=[],
                agreement_score=0.0,
                reasoning_summary="No votes received",
                context_snapshot=proposal.context_snapshot,
            )

        total_confidence = sum(v.confidence for v in votes)
        if total_confidence == 0:
            agreement_score = 0.0
        else:
            agree_weight = sum(v.confidence for v in votes if v.agree) / total_confidence
            agreement_score = agree_weight

        dissenting = [v.voter_node for v in votes if not v.agree]

        # Consensus insight: highest-confidence agreeing vote
        agreeing = [v for v in votes if v.agree]
        if agreeing:
            best = max(agreeing, key=lambda v: v.confidence)
            consensus_insight = best.insight
        else:
            best = max(votes, key=lambda v: v.confidence)
            consensus_insight = best.insight

        reasoning_parts = [f"Node {v.voter_node}: {v.reasoning}" for v in votes if v.reasoning]
        reasoning_summary = " | ".join(reasoning_parts[:5])

        return CognitionState(
            session_id=proposal.session_id,
            participating_nodes=[v.voter_node for v in votes],
            consensus_insight=consensus_insight,
            agreement_score=round(agreement_score, 3),
            dissenting_nodes=dissenting,
            reasoning_summary=reasoning_summary,
            context_snapshot=proposal.context_snapshot,
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "node_id": self._node_id,
            "proposals_handled": self._proposals_handled,
            "consensus_reached": self._consensus_reached,
            "running": self._running,
        }
