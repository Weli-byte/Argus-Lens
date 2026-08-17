"""
Inference Cache — Redis-backed result cache with perceptual hashing,
embedding similarity lookup, duplicate suppression, and temporal sequencing.
"""

from __future__ import annotations

import json
import time
from enum import Enum
from typing import Any, Optional

import numpy as np
import redis.asyncio as aioredis
from loguru import logger
from prometheus_client import Counter, Gauge

try:
    import imagehash
    from PIL import Image
    _IMAGEHASH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _IMAGEHASH_AVAILABLE = False

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_CACHE_HIT = Counter("arguslens_cache_hit_total", "Inference cache hits")
_CACHE_MISS = Counter("arguslens_cache_miss_total", "Inference cache misses")
_CACHE_SIZE = Gauge("arguslens_cache_size_bytes", "Estimated cache size in bytes")

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class CacheStrategy(str, Enum):
    NONE = "NONE"
    FRAME_HASH = "FRAME_HASH"
    EMBEDDING_SIMILARITY = "EMBEDDING_SIMILARITY"
    TEMPORAL_WINDOW = "TEMPORAL_WINDOW"


# Redis key namespaces
_NS_RESULT = "argus:cache:result:{key}"
_NS_EMBED = "argus:cache:embed:{key}"
_NS_EMBED_INDEX = "argus:cache:embed_index"
_NS_DEDUP = "argus:cache:dedup:{request_id}"
_NS_TEMPORAL = "argus:cache:temporal:{session_id}"
_NS_STATS = "argus:cache:stats"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class InferenceCache:
    """
    Layered inference result cache backed by Redis.

    Strategies
    ----------
    FRAME_HASH
        Perceptual hash of the raw frame (imagehash.phash).  Tolerant of minor
        compression artefacts and small photometric changes.

    EMBEDDING_SIMILARITY
        Stores the embedding alongside the result.  ``find_similar_embedding``
        scans the embedding index and returns a cached result whose cosine
        similarity exceeds *threshold*.  Best for semantic deduplication.

    TEMPORAL_WINDOW
        Stores ordered sequences keyed by session.  Allows replaying recent
        frames without re-inference during reconnects.

    DUPLICATE_SUPPRESSION
        Atomic Redis SET with NX+EX to deduplicate concurrent requests within
        a short time window.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        default_ttl: int = 300,
        max_entries: int = 10_000,
    ) -> None:
        self._redis = redis_client
        self.default_ttl = default_ttl
        self.max_entries = max_entries

    # ------------------------------------------------------------------
    # Basic result cache
    # ------------------------------------------------------------------

    async def get_cached_result(self, cache_key: str) -> Optional[dict[str, Any]]:
        """Return cached inference result for *cache_key*, or None on miss."""
        raw = await self._redis.get(_NS_RESULT.format(key=cache_key))
        if raw is None:
            _CACHE_MISS.inc()
            return None
        _CACHE_HIT.inc()
        return json.loads(raw)

    async def cache_result(
        self,
        cache_key: str,
        result: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """Store *result* under *cache_key* with an optional TTL (seconds)."""
        ttl = ttl or self.default_ttl
        serialised = json.dumps(result, default=str)
        await self._redis.setex(_NS_RESULT.format(key=cache_key), ttl, serialised)
        _CACHE_SIZE.inc(len(serialised))

    # ------------------------------------------------------------------
    # Perceptual hashing
    # ------------------------------------------------------------------

    def compute_frame_hash(self, frame: np.ndarray) -> str:
        """
        Compute a perceptual hash of *frame* using DCT-based phash.
        Falls back to a SHA-256 hex digest when imagehash is unavailable.
        """
        if _IMAGEHASH_AVAILABLE:
            pil_img = Image.fromarray(frame)
            phash = imagehash.phash(pil_img, hash_size=16)
            return str(phash)

        # Fallback: deterministic but not perceptual
        import hashlib
        flat = frame.astype(np.uint8).tobytes()
        return hashlib.sha256(flat).hexdigest()

    # ------------------------------------------------------------------
    # Embedding similarity cache
    # ------------------------------------------------------------------

    async def find_similar_embedding(
        self,
        embedding: np.ndarray,
        threshold: float = 0.95,
    ) -> Optional[dict[str, Any]]:
        """
        Scan the embedding index for a cached result whose embedding has
        cosine similarity ≥ *threshold* to *embedding*.

        Implementation note: this is an O(n) linear scan over the index,
        suitable for caches up to ~10 k entries.  For larger scales, use
        pgvector or a vector DB instead.
        """
        query = embedding / (np.linalg.norm(embedding) + 1e-9)

        index_keys: list[str] = await self._redis.lrange(_NS_EMBED_INDEX, 0, -1)  # type: ignore[assignment]
        for embed_key in index_keys:
            raw = await self._redis.get(_NS_EMBED.format(key=embed_key))
            if raw is None:
                continue
            entry = json.loads(raw)
            cached_vec = np.array(entry["embedding"], dtype=np.float32)
            cached_vec /= np.linalg.norm(cached_vec) + 1e-9
            similarity = float(np.dot(query, cached_vec))
            if similarity >= threshold:
                result = await self.get_cached_result(embed_key)
                if result is not None:
                    logger.debug("Embedding cache hit key={} similarity={:.3f}", embed_key, similarity)
                    return result

        _CACHE_MISS.inc()
        return None

    async def store_embedding_result(
        self,
        cache_key: str,
        embedding: np.ndarray,
        result: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """Store result + embedding for similarity-based retrieval."""
        ttl = ttl or self.default_ttl
        embed_payload = json.dumps({"embedding": embedding.tolist()})
        pipe = self._redis.pipeline()
        pipe.setex(_NS_EMBED.format(key=cache_key), ttl, embed_payload)
        pipe.lpush(_NS_EMBED_INDEX, cache_key)
        pipe.ltrim(_NS_EMBED_INDEX, 0, self.max_entries - 1)
        await pipe.execute()
        await self.cache_result(cache_key, result, ttl)

    # ------------------------------------------------------------------
    # Duplicate suppression
    # ------------------------------------------------------------------

    async def suppress_duplicate_request(
        self,
        request_id: str,
        window_ms: int = 100,
    ) -> bool:
        """
        Return True if *request_id* has already been seen within *window_ms*
        milliseconds (i.e. this is a duplicate and should be suppressed).
        Uses atomic SET NX + EX for race-free deduplication.
        """
        key = _NS_DEDUP.format(request_id=request_id)
        ttl_s = max(1, window_ms // 1000)
        # SET key "1" NX EX ttl — only sets if key doesn't exist
        acquired = await self._redis.set(key, "1", nx=True, ex=ttl_s)
        is_duplicate = acquired is None  # None means key already existed
        if is_duplicate:
            logger.debug("Duplicate request suppressed id={}", request_id)
        return is_duplicate

    # ------------------------------------------------------------------
    # Temporal sequence cache
    # ------------------------------------------------------------------

    async def cache_temporal_sequence(
        self,
        session_id: str,
        sequence: list[dict[str, Any]],
        ttl: int = 60,
    ) -> None:
        """
        Store an ordered sequence of frame results for replay on reconnect.
        Each entry is appended to a Redis list; the list is capped at 500
        entries to bound memory usage.
        """
        key = _NS_TEMPORAL.format(session_id=session_id)
        pipe = self._redis.pipeline()
        for item in sequence:
            pipe.rpush(key, json.dumps(item, default=str))
        pipe.ltrim(key, -500, -1)
        pipe.expire(key, ttl)
        await pipe.execute()

    async def get_temporal_sequence(
        self,
        session_id: str,
        last_n: int = 30,
    ) -> list[dict[str, Any]]:
        """Retrieve the last *last_n* entries from a session's temporal cache."""
        key = _NS_TEMPORAL.format(session_id=session_id)
        raw_items: list[str] = await self._redis.lrange(key, -last_n, -1)  # type: ignore[assignment]
        return [json.loads(r) for r in raw_items]

    # ------------------------------------------------------------------
    # Cache statistics
    # ------------------------------------------------------------------

    async def get_cache_stats(self) -> dict[str, Any]:
        """Return hit rate, miss rate, and estimated entry count."""
        # Retrieve counters from Prometheus sample values
        hit_total = _CACHE_HIT._value.get()
        miss_total = _CACHE_MISS._value.get()
        total = hit_total + miss_total

        hit_rate = hit_total / total if total > 0 else 0.0
        miss_rate = miss_total / total if total > 0 else 0.0

        embed_index_len = await self._redis.llen(_NS_EMBED_INDEX)

        return {
            "hit_total": int(hit_total),
            "miss_total": int(miss_total),
            "hit_rate": round(hit_rate, 4),
            "miss_rate": round(miss_rate, 4),
            "embed_index_entries": embed_index_len,
        }
