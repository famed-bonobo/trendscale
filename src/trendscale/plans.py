"""Each operation as a plan that names the Google Trends calls it needs and builds its result from their answers,
without doing any network itself, so the sync and the async client run the very same logic.

A plan yields one call and is sent its answer, or yields a list of calls and is sent a list of outcomes, each an
answer or the exception that call ended with.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar
from urllib.parse import quote

from . import anchoring
from ._protocol import constants
from ._protocol.explore_parser import parse_regions, parse_related_queries, parse_suggestions, parse_timeline
from ._protocol.explore_request import ExploreWidgets, explore_parameters, read_widgets, widget_parameters, widget_url
from ._protocol.trending_parser import explore_url, parse_trending
from .errors import NoDataError, RequestRejectedError
from .options import Search
from .records import Comparison, term_records

T = TypeVar('T')


@dataclass(frozen=True)
class JsonCall:
    """A GET to one of Google Trends' /trends/api endpoints, answered with JSON behind a guard line."""

    url: str
    params: dict[str, str]


@dataclass(frozen=True)
class TrendingCall:
    geo: str
    hours: int


Call = JsonCall | TrendingCall
Plan = Generator[Call | list[Call], Any, T]


@dataclass(frozen=True)
class ExploreOptions:
    separate: bool
    anchor: str
    include_regions: bool
    region_resolution: str
    include_low_volume_regions: bool
    include_related_queries: bool


def explore(search: Search, options: ExploreOptions, language: str) -> Plan[list[dict[str, Any]]]:
    """One record per term; unless `separate`, every term is on one 0-100 scale, chained through the anchor past five."""
    if options.separate:
        groups, mode = [[term] for term in search.terms], 'separate'
    elif len(search.terms) <= constants.MAX_TERMS_PER_COMPARISON:
        groups, mode = [list(search.terms)], 'together'
    else:
        groups, mode = anchoring.split_batches(list(search.terms), options.anchor), 'anchored'
    comparisons = yield from _fetch(search, groups, options, language)
    return term_records(search, mode, options.anchor, comparisons, language)


def trending_now(geo: str, hours: int, limit: int | None) -> Plan[list[dict[str, Any]]]:
    """What people search for right now in one country, in Google's order."""
    rows = parse_trending((yield TrendingCall(geo, hours)), geo)[:limit]
    scraped_at = datetime.now(UTC).isoformat(timespec='seconds')
    for row in rows:
        row.update(hours=hours, trendsUrl=explore_url(row['query'], geo, hours), scrapedAt=scraped_at)
    return rows


def suggestions(text: str, language: str) -> Plan[list[dict[str, Any]]]:
    """The topics Google suggests for a text, with the Knowledge Graph id that makes a search exact ("/m/05z1_")."""
    params = {'hl': language, 'tz': str(constants.UTC_OFFSET_MINUTES)}
    data = yield JsonCall(f'{constants.AUTOCOMPLETE_URL}/{quote(text, safe="")}', params)
    return [{'searchedText': text, **suggestion} for suggestion in parse_suggestions(data)]


def _fetch(search: Search, groups: list[list[str]], options: ExploreOptions, language: str) -> Plan[list[Comparison]]:
    """Every group's explore call together, then every chart of every group together."""
    answers = _raise_first_failure((yield [_explore_call(search, terms, language) for terms in groups]))
    widgets = [read_widgets(answer.get('widgets', [])) for answer in answers]
    for terms, found in zip(groups, widgets, strict=True):
        if found.timeline is None:
            raise NoDataError(f'Google has no timeline for {terms} in {search.geo or "the world"} over {search.time_range!r}')
    charts = [_chart_calls(found, len(terms), options, language) for terms, found in zip(groups, widgets, strict=True)]
    outcomes = iter((yield [call for group in charts for call in group if call is not None]))
    comparisons = []
    for terms, found, group in zip(groups, widgets, charts, strict=True):
        replies = [next(outcomes) if call is not None else None for call in group]
        resolution = (found.timeline or {})['request']['resolution']
        comparisons.append(_comparison(terms, resolution, replies))
    return comparisons


def _explore_call(search: Search, terms: list[str], language: str) -> JsonCall:
    params = explore_parameters(terms, search.geo, search.time_range, search.category, search.search_property, language)
    return JsonCall(constants.EXPLORE_URL, params)


def _chart_calls(found: ExploreWidgets, term_count: int, options: ExploreOptions, language: str) -> list[JsonCall | None]:
    """The timeline, the compared regions and each term's related queries; None for a chart not asked for or not shown."""

    def call(widget: dict[str, Any] | None) -> JsonCall | None:
        if widget is None:
            return None
        params = widget_parameters(widget, language, options.region_resolution, options.include_low_volume_regions)
        return JsonCall(widget_url(widget), params)

    regions = call(found.regions) if options.include_regions else None
    related = [
        call(found.related_queries.get(position)) if options.include_related_queries else None for position in range(term_count)
    ]
    return [call(found.timeline), regions, *related]


def _comparison(terms: list[str], resolution: str, replies: list[Any]) -> Comparison:
    timeline, regions, *related = replies
    if isinstance(timeline, Exception):
        raise timeline
    granularity, series = parse_timeline(timeline, resolution, len(terms))
    # Google answers 400 when it does not break this search down by the chosen region level; regions are then left out.
    if isinstance(regions, RequestRejectedError):
        regions = None
    elif isinstance(regions, Exception):
        raise regions
    for reply in related:
        if isinstance(reply, Exception):
            raise reply
    return Comparison(
        terms=terms,
        granularity=granularity,
        series=series,
        regions=parse_regions(regions, len(terms)) if regions is not None else None,
        related_queries=[parse_related_queries(reply) if reply is not None else None for reply in related],
    )


def _raise_first_failure(outcomes: list[Any]) -> list[Any]:
    for outcome in outcomes:
        if isinstance(outcome, Exception):
            raise outcome
    return outcomes
