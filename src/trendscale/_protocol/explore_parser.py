"""Reads the data of Google Trends' charts into plain records: timeline points, regions and related searches.

Every /trends/api answer starts with a guard line (")]}'") followed by JSON. Values are Google's own 0-100 scale: the
period's highest point of the highest term of the explore call is 100.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..errors import UnreadableAnswerError
from . import constants as config

# Resolutions whose points are whole days; finer ones carry a time of day.
DAILY_OR_COARSER = {'DAY', 'WEEK', 'MONTH', 'YEAR'}
# Google writes "Breakout" for rising searches that grew by more than 5000 %.
BREAKOUT_LABEL = 'Breakout'
TRENDS_LINK_PREFIX = config.ORIGIN


def strip_guard(text: str) -> Any:
    """The JSON of a /trends/api answer, without its guard line."""
    if not text.startswith(config.RESPONSE_GUARD):
        raise UnreadableAnswerError(f'The answer does not start with {config.RESPONSE_GUARD!r}: {text[:80]!r}')
    try:
        return json.loads(text[text.index('\n') + 1 :])
    except (ValueError, json.JSONDecodeError) as error:
        raise UnreadableAnswerError(f'The answer is not JSON after its guard line: {text[:80]!r}') from error


def parse_timeline(data: dict[str, Any], resolution: str, term_count: int) -> tuple[str, list[list[dict[str, Any]]]]:
    """The granularity ("week", "day"...) and, for each term, its points: ISO date, epoch seconds, value, partial flag."""
    rows = data.get('default', {}).get('timelineData', [])
    series: list[list[dict[str, Any]]] = [[] for _ in range(term_count)]
    for row in rows:
        timestamp = int(row['time'])
        moment = datetime.fromtimestamp(timestamp, tz=UTC)
        label = (
            moment.date().isoformat()
            if resolution in DAILY_OR_COARSER
            else moment.isoformat(timespec='seconds').replace('+00:00', 'Z')
        )
        for index in range(term_count):
            series[index].append(
                {
                    'date': label,
                    'timestamp': timestamp,
                    'value': row['value'][index],
                    'hasData': bool(row['hasData'][index]),
                    'isPartial': bool(row.get('isPartial', False)),
                }
            )
    return resolution.lower() or 'unknown', series


def parse_regions(data: dict[str, Any], term_count: int) -> list[list[dict[str, Any]]]:
    """For each term, its regions with a value, highest first: code (cities have none), name, 0-100 value, coordinates."""
    regions: list[list[dict[str, Any]]] = [[] for _ in range(term_count)]
    for row in data.get('default', {}).get('geoMapData', []):
        coordinates = row.get('coordinates') or {}
        for index in range(term_count):
            if row['hasData'][index]:
                regions[index].append(
                    {
                        'geoCode': row.get('geoCode'),
                        'geoName': row['geoName'],
                        'value': row['value'][index],
                        'latitude': coordinates.get('lat'),
                        'longitude': coordinates.get('lng'),
                    }
                )
    for entries in regions:
        entries.sort(key=lambda entry: -entry['value'])
    return regions


def parse_related_queries(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Top and rising related queries; a rising query's value is its growth in percent, or Breakout above 5000 %."""
    top, rising = _ranked_lists(data)
    return {
        'top': [{'query': item['query'], 'value': item['value'], 'trendsUrl': _absolute(item.get('link'))} for item in top],
        'rising': [_rising_query(item) for item in rising],
    }


def parse_suggestions(data: dict[str, Any]) -> list[dict[str, Any]]:
    """The topics Google's search box suggests for a text: Knowledge Graph id, title and kind ("Programming language")."""
    return [
        {'rank': rank, 'topicId': topic['mid'], 'title': topic['title'], 'kind': topic.get('type')}
        for rank, topic in enumerate(data.get('default', {}).get('topics', []), start=1)
    ]


def timeline_summary(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Average, peak and latest value of a term's complete points (the partial last one is left out of the average)."""
    complete = [point for point in points if not point['isPartial']] or points
    if not complete:
        return {'average': None, 'peakValue': None, 'peakDate': None, 'latestValue': None}
    peak = max(complete, key=lambda point: point['value'])
    return {
        'average': round(sum(point['value'] for point in complete) / len(complete), 1),
        'peakValue': peak['value'],
        'peakDate': peak['date'],
        'latestValue': points[-1]['value'],
    }


def _ranked_lists(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lists = data.get('default', {}).get('rankedList', [])
    top = lists[0].get('rankedKeyword', []) if len(lists) > 0 else []
    rising = lists[1].get('rankedKeyword', []) if len(lists) > 1 else []
    return top, rising


def _rising_query(item: dict[str, Any]) -> dict[str, Any]:
    return {
        'query': item['query'],
        'value': item['value'],
        'isBreakout': item.get('formattedValue') == BREAKOUT_LABEL,
        'trendsUrl': _absolute(item.get('link')),
    }


def _absolute(link: str | None) -> str | None:
    return f'{TRENDS_LINK_PREFIX}{link}' if link else None
