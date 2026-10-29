"""Drives a plan to its result: sends each call it names through a transport and hands the answers back to it.

A batch of calls goes out together in both: on a few threads in the sync runner and as tasks in the async one. Either
way the transport's pace decides how fast requests actually leave this machine.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from .errors import TrendsError
from .plans import Call, JsonCall, Plan
from .transport import AsyncTransport, SyncTransport

T = TypeVar('T')


def run_sync(plan: Plan[T], transport: SyncTransport) -> T:
    reply: Any = None
    failure: TrendsError | None = None
    while True:
        try:
            step = plan.throw(failure) if failure else plan.send(reply)
        except StopIteration as finished:
            result: T = finished.value
            return result
        failure = None
        if isinstance(step, list):
            with ThreadPoolExecutor(max_workers=transport.max_concurrency) as pool:
                reply = list(pool.map(lambda call: _outcome_sync(transport, call), step))
            continue
        try:
            reply = _send_sync(transport, step)
        except TrendsError as error:
            failure = error


async def run_async(plan: Plan[T], transport: AsyncTransport) -> T:
    reply: Any = None
    failure: TrendsError | None = None
    while True:
        try:
            step = plan.throw(failure) if failure else plan.send(reply)
        except StopIteration as finished:
            result: T = finished.value
            return result
        failure = None
        if isinstance(step, list):
            reply = await asyncio.gather(*(_outcome_async(transport, call) for call in step))
            continue
        try:
            reply = await _send_async(transport, step)
        except TrendsError as error:
            failure = error


def _send_sync(transport: SyncTransport, call: Call) -> Any:
    if isinstance(call, JsonCall):
        return transport.get_json(call.url, call.params)
    return transport.trending(call.geo, call.hours)


async def _send_async(transport: AsyncTransport, call: Call) -> Any:
    if isinstance(call, JsonCall):
        return await transport.get_json(call.url, call.params)
    return await transport.trending(call.geo, call.hours)


def _outcome_sync(transport: SyncTransport, call: Call) -> Any:
    try:
        return _send_sync(transport, call)
    except TrendsError as error:
        return error


async def _outcome_async(transport: AsyncTransport, call: Call) -> Any:
    try:
        return await _send_async(transport, call)
    except TrendsError as error:
        return error
