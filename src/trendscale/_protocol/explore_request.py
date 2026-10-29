"""Builds the query strings of Google Trends' explore call and of each chart's data call, and picks the charts of an
explore answer.

An explore call names up to five terms (each with its region and period) and returns one widget per chart. A widget
carries the request and the token its data call needs. Terms compared in one explore call share a 0-100 scale.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from . import constants as config

WIDGET_ID = re.compile(rf'^({config.TIMELINE_WIDGET}|{config.REGIONS_WIDGET}|{config.RELATED_QUERIES_WIDGET})(?:_(\d+))?$')
COMPACT_SEPARATORS = (',', ':')
# Region breakdown levels as Google's request names them.
RESOLUTIONS = {'country': 'COUNTRY', 'region': 'REGION', 'city': 'CITY', 'dma': 'DMA'}


@dataclass
class ExploreWidgets:
    """The charts of an explore answer: the timeline and regions shared by all its terms, and each term's related queries."""

    timeline: dict[str, Any] | None = None
    regions: dict[str, Any] | None = None
    related_queries: dict[int, dict[str, Any]] = field(default_factory=dict)


def explore_parameters(
    terms: list[str],
    geo: str,
    time_range: str,
    category: int,
    search_property: str,
    language: str,
) -> dict[str, str]:
    """The query string of an explore call for terms compared on one scale."""
    request = {
        'comparisonItem': [{'keyword': term, 'geo': geo, 'time': time_range} for term in terms],
        'category': category,
        'property': search_property,
    }
    return {
        'hl': language,
        'tz': str(config.UTC_OFFSET_MINUTES),
        'req': json.dumps(request, separators=COMPACT_SEPARATORS, ensure_ascii=False),
    }


def trends_page_url(terms: list[str], geo: str, time_range: str, category: int, search_property: str) -> str:
    """The trends.google.com page that charts these terms, to open the same comparison in the browser."""
    parameters = {'q': ','.join(terms), 'date': time_range}
    if geo:
        parameters['geo'] = geo
    if category:
        parameters['cat'] = str(category)
    if search_property:
        parameters['gprop'] = search_property
    return f'{config.LANDING_URL}?{urlencode(parameters)}'


def widget_url(widget: dict[str, Any]) -> str:
    return f'{config.WIDGET_DATA_URL}/{config.WIDGET_ENDPOINTS[_kind_of(widget)]}'


def widget_parameters(widget: dict[str, Any], language: str, region_resolution: str, include_low_volume: bool) -> dict[str, str]:
    """The query string of a chart's data call: its own request and token, with the region level the caller asked for."""
    request = dict(widget['request'])
    if _kind_of(widget) == config.REGIONS_WIDGET:
        if region_resolution != 'auto':
            request['resolution'] = RESOLUTIONS[region_resolution]
        request['includeLowSearchVolumeGeos'] = include_low_volume
    return {
        'hl': language,
        'tz': str(config.UTC_OFFSET_MINUTES),
        'req': json.dumps(request, separators=COMPACT_SEPARATORS, ensure_ascii=False),
        'token': widget['token'],
    }


def read_widgets(widgets: list[dict[str, Any]]) -> ExploreWidgets:
    """Sort an explore answer's widgets into the shared charts and each term's related queries.

    The timeline and the compared regions keep their plain ids. One term's related queries have a plain id too;
    with several terms each carries the term's position (RELATED_QUERIES_0, RELATED_QUERIES_1...). The per-term
    region maps (GEO_MAP_0...) are not read: each is scaled on its own, so only the compared one is comparable.
    """
    found = ExploreWidgets()
    for widget in widgets:
        match = WIDGET_ID.match(widget.get('id', ''))
        if not match:
            continue
        kind, position = match.group(1), match.group(2)
        if kind == config.TIMELINE_WIDGET:
            found.timeline = widget
        elif kind == config.REGIONS_WIDGET and position is None:
            found.regions = widget
        elif kind == config.RELATED_QUERIES_WIDGET:
            found.related_queries[int(position or 0)] = widget
    return found


def _kind_of(widget: dict[str, Any]) -> str:
    match = WIDGET_ID.match(widget['id'])
    if not match:
        raise ValueError(f'Unknown widget id {widget["id"]!r}')
    return match.group(1)
