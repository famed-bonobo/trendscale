"""Turns the fetched comparisons of a search into one record per term, with every term on one scale when compared.

Records use the same field names as the hosted Google Trends Scraper on Apify, so code that reads one reads the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from . import anchoring
from ._protocol import constants
from ._protocol.explore_parser import timeline_summary
from ._protocol.explore_request import trends_page_url
from .options import Search

# Tells the reader why anchored values differ from the numbers trends.google.com shows for the same term.
ANCHOR_SCALE_NOTE = 'values are rescaled through the anchor term so all terms share one 0-100 scale'


@dataclass
class Comparison:
    """What Google shows for one explore call of up to five terms."""

    terms: list[str]
    granularity: str
    series: list[list[dict[str, Any]]]
    # None when the regions were not asked for or Google does not break the search down by the chosen level.
    regions: list[list[dict[str, Any]]] | None
    # One entry per term; None when not asked for or Google showed none for that term.
    related_queries: list[dict[str, list[dict[str, Any]]] | None]


def term_records(search: Search, mode: str, anchor: str, comparisons: list[Comparison], language: str) -> list[dict[str, Any]]:
    """One record per term, in the order asked; in an anchored search the anchor is kept only if it was asked for."""
    rescaled = _rescale(comparisons, anchor) if mode == 'anchored' else None
    scraped_at = datetime.now(UTC).isoformat(timespec='seconds')
    by_term: dict[str, dict[str, Any]] = {}
    for comparison in comparisons:
        for position, term in enumerate(comparison.terms):
            if term in search.terms and term not in by_term:
                by_term[term] = _record(search, mode, comparison, position, rescaled, language, scraped_at)
    records = [by_term[term] for term in search.terms if term in by_term]
    if rescaled:
        for record in records:
            record['anchor'] = {'term': anchor, 'note': ANCHOR_SCALE_NOTE, 'isPrecise': not rescaled.imprecise_batches}
    return records


def _rescale(comparisons: list[Comparison], anchor: str) -> anchoring.AnchoredResult:
    values = [
        {term: [point['value'] for point in series] for term, series in zip(comparison.terms, comparison.series, strict=True)}
        for comparison in comparisons
    ]
    return anchoring.rescale(values, anchor)


def _record(
    search: Search,
    mode: str,
    comparison: Comparison,
    position: int,
    rescaled: anchoring.AnchoredResult | None,
    language: str,
    scraped_at: str,
) -> dict[str, Any]:
    term = comparison.terms[position]
    timeline = comparison.series[position]
    if rescaled:
        timeline = [{**point, 'value': value} for point, value in zip(timeline, rescaled.terms[term].values, strict=True)]
    compared_with = [] if mode == 'separate' else [other for other in search.terms if other != term]
    return {
        'term': term,
        'geo': search.geo,
        'timeRange': search.time_range,
        'searchType': constants.SEARCH_TYPE_OF_PROPERTY[search.search_property],
        'category': search.category,
        'language': language,
        'comparison': mode,
        'comparedWith': compared_with,
        'granularity': comparison.granularity,
        'timeline': timeline,
        'summary': timeline_summary(timeline),
        'regions': comparison.regions[position] if comparison.regions else None,
        'relatedQueries': comparison.related_queries[position],
        'trendsUrl': trends_page_url(comparison.terms, search.geo, search.time_range, search.category, search.search_property),
        'scrapedAt': scraped_at,
    }
