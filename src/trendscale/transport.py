"""Sends Google Trends calls from this machine's IP at the pace Google tolerates, and rests the IP while Google blocks it.

Explore calls need Google's NID cookie: a call without it is answered 429 and handed the cookie, so the next call
works. That first 429 is therefore not a block and is retried at once. Later 429s are blocks: the pace halves and the
IP rests, 45 s at first and longer if the block persists, as measured against Google in October 2026.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

from ._protocol import constants
from ._protocol.explore_parser import strip_guard
from ._protocol.ip_pace import IpPace, PaceLimits
from ._protocol.trending_parser import batch_payload
from ._protocol.trending_request import trending_form, trending_parameters
from .errors import RequestRejectedError, TrendsBlockedError, UnreadableAnswerError

T = TypeVar('T')
TOO_MANY_REQUESTS, BAD_REQUEST, OK = 429, 400, 200
MAX_ATTEMPTS = 8
# A call gives up once its waits for the IP's pace and rests add up to this.
MAX_WAIT_SECONDS = 180
PACE_LIMITS = PaceLimits(
    initial_rate=constants.IP_RATE_INITIAL,
    minimum_rate=constants.IP_RATE_MINIMUM,
    maximum_rate=constants.IP_RATE_MAXIMUM,
    rate_step=constants.IP_RATE_STEP,
    first_rest_seconds=constants.BLOCKED_IP_FIRST_REST_SECONDS,
    longest_rest_seconds=constants.BLOCKED_IP_LONGEST_REST_SECONDS,
    refusals_before_rest=constants.REFUSALS_BEFORE_REST,
)
Reader = Callable[[str], Any]


def _client_options(language: str, proxy: str | None) -> dict[str, Any]:
    headers = {**constants.REQUEST_HEADERS, 'Accept-Language': f'{language},en;q=0.8'}
    return {'proxy': proxy, 'headers': headers, 'timeout': constants.REQUEST_TIMEOUT_SECONDS, 'follow_redirects': True}


def _has_cookie(cookies: httpx.Cookies) -> bool:
    return any(cookie.name == constants.COOKIE_NAME for cookie in cookies.jar)


def _judge(pace: IpPace, started: float, response: httpx.Response | None, was_cold: bool, read: Reader) -> tuple[Any, str | None]:
    """The answer's data and None, or None and why to try again; teaches the pace what Google did."""
    if response is None:
        pace.note_refusal(started)
        return None, 'network error'
    if response.status_code == BAD_REQUEST:
        raise RequestRejectedError(f'Google rejected {response.url} with HTTP 400; this request cannot succeed as it is')
    if response.status_code == TOO_MANY_REQUESTS:
        pace.record(started, was_blocked=not was_cold)
        return None, 'HTTP 429 before the cookie' if was_cold else 'HTTP 429 (rate-limited)'
    if response.status_code != OK:
        pace.note_refusal(started)
        return None, f'HTTP {response.status_code}'
    try:
        value = read(response.text)
    except UnreadableAnswerError as error:
        pace.note_refusal(started)
        return None, str(error)
    pace.record(started, was_blocked=False)
    pace.note_data()
    return value, None


def _blocked(url: str, problem: str | None) -> TrendsBlockedError:
    return TrendsBlockedError(
        f'Gave up on {url}: {problem}. Google is rate-limiting this IP; wait a few minutes, '
        'make fewer calls at once, or pass a proxy.'
    )


class SyncTransport:
    def __init__(self, language: str, proxy: str | None, max_concurrency: int) -> None:
        self._language = language
        self._http = httpx.Client(**_client_options(language, proxy))
        self._pace = IpPace(PACE_LIMITS)
        self._lock = threading.Lock()
        self.max_concurrency = max_concurrency

    def close(self) -> None:
        self._http.close()

    def get_json(self, url: str, params: dict[str, str]) -> Any:
        return self._call('GET', url, strip_guard, params=params)

    def trending(self, geo: str, hours: int) -> Any:
        return self._call(
            'POST',
            constants.BATCH_URL,
            lambda text: batch_payload(text, constants.TRENDING_NOW_RPC),
            params=trending_parameters(self._language),
            data=trending_form(geo, hours, self._language),
        )

    def _call(self, method: str, url: str, read: Reader, **request: Any) -> Any:
        problem: str | None = 'no attempt made'
        waited = 0.0
        for _attempt in range(MAX_ATTEMPTS):
            started, waited = self._take_turn(url, waited, problem)
            was_cold = not _has_cookie(self._http.cookies)
            try:
                response: httpx.Response | None = self._http.request(method, url, **request)
            except httpx.HTTPError:
                response = None
            value, problem = _judge(self._pace, started, response, was_cold, read)
            if problem is None:
                return value
        raise _blocked(url, problem)

    def _take_turn(self, url: str, waited: float, problem: str | None) -> tuple[float, float]:
        while True:
            with self._lock:
                wait = max(self._pace.wait_seconds(), self._pace.rest_remaining())
                if wait == 0:
                    return self._pace.take_turn(), waited
            if waited + wait > MAX_WAIT_SECONDS:
                raise _blocked(url, problem)
            time.sleep(wait)
            waited += wait


class AsyncTransport:
    def __init__(self, language: str, proxy: str | None, max_concurrency: int) -> None:
        self._language = language
        self._http = httpx.AsyncClient(**_client_options(language, proxy))
        self._pace = IpPace(PACE_LIMITS)
        self._lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(max_concurrency)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_json(self, url: str, params: dict[str, str]) -> Any:
        return await self._call('GET', url, strip_guard, params=params)

    async def trending(self, geo: str, hours: int) -> Any:
        return await self._call(
            'POST',
            constants.BATCH_URL,
            lambda text: batch_payload(text, constants.TRENDING_NOW_RPC),
            params=trending_parameters(self._language),
            data=trending_form(geo, hours, self._language),
        )

    async def _call(self, method: str, url: str, read: Reader, **request: Any) -> Any:
        problem: str | None = 'no attempt made'
        waited = 0.0
        for _attempt in range(MAX_ATTEMPTS):
            async with self._slots:
                started, waited = await self._take_turn(url, waited, problem)
                was_cold = not _has_cookie(self._http.cookies)
                response = await self._send(method, url, request)
                value, problem = _judge(self._pace, started, response, was_cold, read)
            if problem is None:
                return value
        raise _blocked(url, problem)

    async def _send(self, method: str, url: str, request: dict[str, Any]) -> httpx.Response | None:
        # The read timeout never fires while a throttled connection trickles bytes, so each attempt has a total deadline.
        try:
            async with asyncio.timeout(constants.ATTEMPT_DEADLINE_SECONDS):
                return await self._http.request(method, url, **request)
        except (TimeoutError, httpx.HTTPError):
            return None

    async def _take_turn(self, url: str, waited: float, problem: str | None) -> tuple[float, float]:
        while True:
            async with self._lock:
                wait = max(self._pace.wait_seconds(), self._pace.rest_remaining())
                if wait == 0:
                    return self._pace.take_turn(), waited
            if waited + wait > MAX_WAIT_SECONDS:
                raise _blocked(url, problem)
            await asyncio.sleep(wait)
            waited += wait
