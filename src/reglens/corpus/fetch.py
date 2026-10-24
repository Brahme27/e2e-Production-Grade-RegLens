"""Polite HTTP fetching: robots.txt, per-host delay, retries and an on-disk cache.

Every byte we download is cached under ``data/raw/.http-cache`` keyed by URL, so a re-run
of the crawler costs the regulators' servers nothing and works offline.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from reglens.log import get_logger

log = get_logger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
HTTP_OK = 200
HTTP_NOT_FOUND = 404


class FetchError(RuntimeError):
    """A URL could not be fetched (blocked by robots.txt, 4xx, or retries exhausted)."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status: int
    content_type: str
    content: bytes
    fetched_at: str
    from_cache: bool

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


class PoliteFetcher:
    """GET with robots.txt checks, a minimum delay per host, retries and a disk cache."""

    def __init__(
        self,
        cache_dir: Path,
        user_agent: str,
        *,
        delay_seconds: float = 1.5,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache_dir = cache_dir
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self._sleep = sleep
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            follow_redirects=True,
            transport=transport,
        )

    # ---------- cache ----------
    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        folder = self.cache_dir / key[:2]
        return folder / f"{key}.bin", folder / f"{key}.json"

    def _read_cache(self, url: str) -> FetchResult | None:
        body_path, meta_path = self._cache_paths(url)
        if not (body_path.exists() and meta_path.exists()):
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return FetchResult(content=body_path.read_bytes(), from_cache=True, **meta)

    def _write_cache(self, result: FetchResult) -> None:
        body_path, meta_path = self._cache_paths(result.url)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(result.content)
        meta = {
            "url": result.url,
            "final_url": result.final_url,
            "status": result.status,
            "content_type": result.content_type,
            "fetched_at": result.fetched_at,
        }
        meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")

    # ---------- politeness ----------
    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                response = self._client.get(f"{host}/robots.txt")
                if response.status_code == HTTP_OK:
                    parser.parse(response.text.splitlines())  # type: ignore[union-attr]
                else:  # no robots.txt (or an error page): nothing is disallowed
                    parser = None
            except httpx.HTTPError:
                parser = None
            self._robots[host] = parser
        robots = self._robots[host]
        return robots is None or robots.can_fetch(self.user_agent, url)

    def _wait_turn(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            remaining = self.delay_seconds - (time.monotonic() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_hit[host] = time.monotonic()

    # ---------- public ----------
    def get(self, url: str, *, use_cache: bool = True) -> FetchResult:
        if use_cache and (cached := self._read_cache(url)) is not None:
            return cached
        if not self.allowed(url):
            raise FetchError(f"robots.txt disallows {url}")
        host = urlsplit(url).netloc
        last_error = ""
        for attempt in range(self.max_retries + 1):
            self._wait_turn(host)
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == HTTP_OK:
                    result = FetchResult(
                        url=url,
                        final_url=str(response.url),
                        status=response.status_code,
                        content_type=response.headers.get("content-type", ""),
                        content=response.content,
                        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                        from_cache=False,
                    )
                    self._write_cache(result)
                    log.info("fetched", url=url, bytes=len(result.content))
                    return result
                last_error = f"HTTP {response.status_code}"
                if response.status_code not in RETRY_STATUSES:
                    break
            backoff = self.delay_seconds * (2**attempt)
            log.warning("fetch_retry", url=url, attempt=attempt + 1, error=last_error)
            self._sleep(backoff)
        raise FetchError(f"could not fetch {url}: {last_error}")

    def close(self) -> None:
        self._client.close()
