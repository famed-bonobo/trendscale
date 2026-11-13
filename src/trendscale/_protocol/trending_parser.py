"""Reads the list of trends that Google Trends' "Trending now" page embeds into plain records.

The list holds one positional array per trend (layout checked against live answers on 2026-10-17 and 2026-11-12):
0 search text, 1 news articles or null, 2 region, 3 [start time], 4 [end time] or null while it still trends,
6 searches in the period as a lower bound (1000 means "1K+"), 8 growth in percent, 9 related searches,
10 category ids, 11 news tokens, 12 normalized text.
"""

from __future__ import annotations

import json
import re
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
# The page names its data requests as 'ds:N' : {id:'\/Service.Method', ...} and fills each from a script block.
DATA_REQUEST = r"'(ds:\d+)'\s*:\s*\{{id:'\\?/{service}'"
DATA_BLOCK = r"AF_initDataCallback\(\{{key: '{key}', hash: '\d+', data:(.*?), sideChannel: \{{"


def embedded_payload(html: str) -> Any:
    """The list of trends inside the page: the data of its FeTrendingService.ListTrends request."""
    request = re.search(DATA_REQUEST.format(service=re.escape(config.TRENDING_SERVICE)), html)
    if not request:
        raise UnreadableAnswerError(f'The page names no {config.TRENDING_SERVICE} request: {html[:80]!r}')
    key = request.group(1)
    block = re.search(DATA_BLOCK.format(key=key), html, re.DOTALL)
    if not block:
        raise UnreadableAnswerError(f'The page holds no data for its {config.TRENDING_SERVICE} request ({key})')
    try:
        return json.loads(block.group(1))
    except ValueError as error:
        raise UnreadableAnswerError(f'The data of {key} is not JSON: {block.group(1)[:80]!r}') from error


def parse_trending(payload: Any, geo: str, earliest_start: datetime | None = None) -> list[dict[str, Any]]:
    """The trends of one region, in Google's order (by search volume), each with its rank.

    With `earliest_start`, only the trends that started at that time or later are kept and ranked.
    """
    try:
        items = [item for item in payload[1] if earliest_start is None or item[3][0] >= earliest_start.timestamp()]
        return [_trend(rank, item, geo) for rank, item in enumerate(items, start=1)]
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
