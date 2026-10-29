"""Reads Google Trends' "Trending now" answer (a batchexecute call) into plain records.

The answer is a list of trends, each a positional array (layout checked against live answers on 2026-10-17):
0 search text, 1 news articles or null, 2 region, 3 [start time], 4 [end time] or null while it still trends,
6 searches in the period as a lower bound (1000 means "1K+"), 8 growth in percent, 9 related searches,
10 category ids, 11 news tokens, 12 normalized text.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from ..errors import UnreadableAnswerError
from . import constants as config

# Category ids of the "Trending now" page's category filter, in English.
TREND_CATEGORIES = {
    1: 'Autos and Vehicles',
    2: 'Beauty and Fashion',
    3: 'Business and Finance',
    4: 'Entertainment',
    5: 'Food and Drink',
    6: 'Games',
    7: 'Health',
    8: 'Hobbies and Leisure',
    9: 'Jobs and Education',
    10: 'Law and Government',
    11: 'Other',
    13: 'Pets and Animals',
    14: 'Politics',
    15: 'Science',
    16: 'Shopping',
    17: 'Sports',
    18: 'Technology',
    19: 'Travel and Transportation',
    20: 'Climate',
}
HOURS_PER_DAY = 24
THOUSAND = 1_000
MILLION = 1_000_000
BATCH_ENTRY_MARKER = 'wrb.fr'


def batch_payload(text: str, rpc_id: str) -> Any:
    """The JSON payload an RPC of a batchexecute answer returns (the answer is a guard line, a blank line and one JSON line)."""
    if not text.startswith(config.RESPONSE_GUARD):
        raise UnreadableAnswerError(f'The batch answer does not start with {config.RESPONSE_GUARD!r}: {text[:80]!r}')
    for line in text.splitlines():
        if not line.startswith('[['):
            continue
        for entry in json.loads(line):
            if entry[0] == BATCH_ENTRY_MARKER and entry[1] == rpc_id:
                if entry[2] is None:
                    raise UnreadableAnswerError(f'Google answered {rpc_id} without data: {line[:120]!r}')
                return json.loads(entry[2])
    raise UnreadableAnswerError(f'The batch answer has no {rpc_id} entry: {text[:120]!r}')


def parse_trending(payload: Any, geo: str) -> list[dict[str, Any]]:
    """The trends of one region, in Google's order (by search volume), each with its rank."""
    try:
        return [_trend(rank, item, geo) for rank, item in enumerate(payload[1], start=1)]
    except (IndexError, TypeError, KeyError) as error:
        raise UnreadableAnswerError(f'Trending now for {geo} has an unexpected layout: {str(payload)[:160]!r}') from error


def explore_url(query: str, geo: str, hours: int) -> str:
    """The Trends page that charts a trending search over the period it was trending in."""
    period = f'now {hours // HOURS_PER_DAY}-d' if hours % HOURS_PER_DAY == 0 else f'now {hours}-H'
    return f'{config.ORIGIN}/trends/explore?{urlencode({"q": query, "date": period, "geo": geo})}'


def volume_label(searches: int) -> str:
    """Google's own wording of a volume bucket: 500 -> "500+", 20000 -> "20K+", 2000000 -> "2M+"."""
    if searches >= MILLION:
        return f'{searches // MILLION}M+'
    if searches >= THOUSAND:
        return f'{searches // THOUSAND}K+'
    return f'{searches}+'


def _trend(rank: int, item: list[Any], geo: str) -> dict[str, Any]:
    started, ended = _moment(item[3]), _moment(item[4])
    return {
        'rank': rank,
        'query': item[0],
        'geo': item[2] or geo,
        'startedAt': started,
        'endedAt': ended,
        'isActive': ended is None,
        'searchVolume': item[6],
        'searchVolumeLabel': volume_label(item[6]) if item[6] else None,
        'volumeGrowthPercent': item[8],
        'relatedQueries': [query for query in item[9] or [] if query != item[0]],
        'categories': [{'id': category, 'name': TREND_CATEGORIES.get(category)} for category in item[10] or []],
    }


def _moment(timestamp: list[int] | None) -> str | None:
    """An ISO time in UTC from Google's one-element [epoch seconds] array."""
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp[0], tz=UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')
