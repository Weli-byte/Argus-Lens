"""
WebSocket Lifecycle Manager — session tracking, heartbeat/pong, idle and
ghost-connection cleanup, graceful + forced disconnect, and reconnection.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from fastapi import WebSocket
from loguru import logger
from prometheus_client import Counter, Gauge
from starlette.websockets import WebSocketState

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_ACTIVE_CONNS = Gauge(
    "arguslens_websocket_active_connections",
    "Number of currently active WebSocket sessions",
)
_GHOST_CLEANED = Counter(
    "arguslens_websocket_ghost_cleaned_total",
    "Total ghost (stale TCP) connections cleaned up",
)
_RECONNECT_TOTAL = Counter(
    "arguslens_websocket_reconnect_total",
    "Total WebSocket session reconnections",
)

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class ConnectionState(str, Enum):
    CONNECTING = "CONNECTING"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    RECONNECTING = "RECONNECTING"
    DEAD = "DEAD"


@dataclass
class WebSocketSession:
    session_id: str
    client_id: str
    websocket: WebSocket
    connected_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    state: ConnectionState = ConnectionState.CONNECTING
    message_count: int = 0
    pong_pending: bool = False


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class WebSocketLifecycleManager:
    """
    Full WebSocket session lifecycle:

    * ``register_connection``   — accept + create session
    * ``send_heartbeat``        — send ping frames on schedule
    * ``handle_pong``           — mark session active after pong
    * ``cleanup_idle``          — background task every 60 s
    * ``cleanup_ghost``         — detect TCP-dead connections
    * ``graceful_disconnect``   — send close frame with reason
    * ``force_disconnect``      — hard close (no frame)
    * ``reconnect_session``     — attach a new WebSocket to an existing session
    """

    def __init__(
        self,
        heartbeat_interval: float = 30.0,
        idle_timeout: float = 300.0,
        max_connections: int = 1000,
    ) -> None:
        self.heartbeat_interval = heartbeat_interval
        self.idle_timeout = idle_timeout
        self.max_connections = max_connections

        self._sessions: dict[str, WebSocketSession] = {}
        self._lock = asyncio.Lock()

        self._heartbeat_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._ghost_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(), name="ws_heartbeat"
        )
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(), name="ws_cleanup_idle"
        )
        self._ghost_task = asyncio.create_task(
            self._ghost_cleanup_loop(), name="ws_cleanup_ghost"
        )
        logger.info("WebSocketLifecycleManager started (max={})", self.max_connections)

    async def stop(self) -> None:
        self._running = False
        for task in (self._heartbeat_task, self._cleanup_task, self._ghost_task):
            if task and not task.done():
                task.cancel()
        # Force-close remaining sessions
        for session_id in list(self._sessions):
            await self.force_disconnect(session_id)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_connection(
        self, websocket: WebSocket, client_id: str
    ) -> str:
        """
        Accept the WebSocket and create a new session.
        Raises RuntimeError if the connection limit is reached.
        """
        async with self._lock:
            if len(self._sessions) >= self.max_connections:
                await websocket.close(code=1013, reason="Server connection limit reached")
                raise RuntimeError("WebSocket connection limit reached")

        await websocket.accept()
        session_id = str(uuid.uuid4())
        session = WebSocketSession(
            session_id=session_id,
            client_id=client_id,
            websocket=websocket,
            state=ConnectionState.ACTIVE,
        )
        async with self._lock:
            self._sessions[session_id] = session
        _ACTIVE_CONNS.set(len(self._sessions))
        logger.info("WS registered session={} client={}", session_id, client_id)
        return session_id

    # ------------------------------------------------------------------
    # Heartbeat / pong
    # ------------------------------------------------------------------

    async def send_heartbeat(self, session_id: str) -> bool:
        """Send a ping frame to the client.  Returns False if session is gone."""
        session = self._sessions.get(session_id)
        if session is None or session.state == ConnectionState.DEAD:
            return False
        try:
            await session.websocket.send_json({"type": "ping", "ts": time.time()})
            session.pong_pending = True
            return True
        except Exception as exc:
            logger.warning("Ping failed session={}: {}", session_id, exc)
            await self.force_disconnect(session_id)
            return False

    async def handle_pong(self, session_id: str) -> None:
        """Update last_activity when the client responds to a ping."""
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = time.monotonic()
            session.pong_pending = False
            session.state = ConnectionState.ACTIVE
            session.message_count += 1

    # ------------------------------------------------------------------
    # Activity tracking
    # ------------------------------------------------------------------

    async def record_message(self, session_id: str) -> None:
        """Call on every inbound message to keep last_activity fresh."""
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = time.monotonic()
            session.message_count += 1
            if session.state == ConnectionState.IDLE:
                session.state = ConnectionState.ACTIVE

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.heartbeat_interval)
            for session_id in list(self._sessions):
                await self.send_heartbeat(session_id)

    async def _cleanup_loop(self) -> None:
        """Every 60 s remove sessions that have been idle too long."""
        while self._running:
            await asyncio.sleep(60)
            await self.cleanup_idle_connections()

    async def _ghost_cleanup_loop(self) -> None:
        """Every 90 s check for ghost connections (pending pong but no response)."""
        while self._running:
            await asyncio.sleep(90)
            await self.cleanup_ghost_connections()

    async def cleanup_idle_connections(self) -> list[str]:
        """Disconnect sessions idle longer than *idle_timeout* seconds."""
        now = time.monotonic()
        idle_sessions = [
            sid
            for sid, s in self._sessions.items()
            if (now - s.last_activity) > self.idle_timeout
        ]
        for sid in idle_sessions:
            logger.info("Closing idle session={}", sid)
            await self.graceful_disconnect(sid, reason="idle_timeout")
        return idle_sessions

    async def cleanup_ghost_connections(self) -> list[str]:
        """
        Detect and remove ghost connections: sessions where a ping was sent
        but no pong received within one full heartbeat interval, AND the
        WebSocket is no longer in CONNECTED state.
        """
        ghosts: list[str] = []
        for sid, session in list(self._sessions.items()):
            if not session.pong_pending:
                continue
            ws = session.websocket
            try:
                is_dead = ws.client_state == WebSocketState.DISCONNECTED
            except Exception:
                is_dead = True

            if is_dead:
                logger.warning("Ghost connection detected session={}", sid)
                ghosts.append(sid)
                await self.force_disconnect(sid)
                _GHOST_CLEANED.inc()

        return ghosts

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------

    async def graceful_disconnect(self, session_id: str, reason: str = "server_close") -> None:
        """Send a WebSocket close frame with *reason* then remove the session."""
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.state = ConnectionState.DEAD
        try:
            await session.websocket.send_json({"type": "close", "reason": reason})
            await session.websocket.close(code=1000, reason=reason)
        except Exception:
            pass  # already disconnected at TCP level
        await self._remove_session(session_id)

    async def force_disconnect(self, session_id: str) -> None:
        """Immediately close without a close frame."""
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.state = ConnectionState.DEAD
        try:
            await session.websocket.close(code=1001)
        except Exception:
            pass
        await self._remove_session(session_id)

    async def _remove_session(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
        _ACTIVE_CONNS.set(len(self._sessions))

    # ------------------------------------------------------------------
    # Reconnection
    # ------------------------------------------------------------------

    async def reconnect_session(
        self,
        old_session_id: str,
        new_websocket: WebSocket,
    ) -> str:
        """
        Attach *new_websocket* to the metadata of *old_session_id*, issue a
        new session_id, and return it.  The old connection is cleaned up.
        """
        async with self._lock:
            old_session = self._sessions.pop(old_session_id, None)

        await new_websocket.accept()
        new_session_id = str(uuid.uuid4())

        client_id = old_session.client_id if old_session else "unknown"
        new_session = WebSocketSession(
            session_id=new_session_id,
            client_id=client_id,
            websocket=new_websocket,
            state=ConnectionState.ACTIVE,
            message_count=old_session.message_count if old_session else 0,
        )

        async with self._lock:
            self._sessions[new_session_id] = new_session

        _ACTIVE_CONNS.set(len(self._sessions))
        _RECONNECT_TOTAL.inc()
        logger.info(
            "WS reconnected old_session={} new_session={} client={}",
            old_session_id,
            new_session_id,
            client_id,
        )
        return new_session_id

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_active_sessions(self) -> list[WebSocketSession]:
        return list(self._sessions.values())

    def get_connection_stats(self) -> dict[str, int | float]:
        sessions = list(self._sessions.values())
        now = time.monotonic()
        return {
            "total": len(sessions),
            "active": sum(1 for s in sessions if s.state == ConnectionState.ACTIVE),
            "idle": sum(1 for s in sessions if s.state == ConnectionState.IDLE),
            "reconnecting": sum(1 for s in sessions if s.state == ConnectionState.RECONNECTING),
            "avg_age_s": (
                round(
                    sum(now - s.connected_at for s in sessions) / len(sessions), 1
                )
                if sessions
                else 0.0
            ),
        }
