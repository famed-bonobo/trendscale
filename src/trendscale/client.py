"""The public clients: Trends for plain code and notebooks, AsyncTrends for asyncio code.

Both take the same arguments and return the same records, with the field names of the hosted Google Trends Scraper on
Apify, so code that reads one reads the other.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any, Self

from . import plans
from ._protocol import constants
from .errors import InvalidOptionError
from .options import (
    RegionResolution,
    SearchType,
    check_choice,
    check_language,
    check_number,
    clean_terms,
    make_search,
)
from .runner import run_async, run_sync
from .transport import AsyncTransport, SyncTransport

TrendsRecord = dict[str, Any]
TimeRange = str | tuple[date, date]
DEFAULT_CONCURRENCY = 4
MAX_CONCURRENCY = 20
MAX_TRENDS_PER_GEO = 1000


class _Planner:
    """Turns a public call's arguments into the plan that answers it; shared by both clients."""

    def __init__(self, language: str) -> None:
        self.language = check_language(language)

    def explore(
        self,
        terms: Iterable[str] | str,
        geo: str,
        time_range: TimeRange,
        category: int,
        search_type: SearchType,
        separate: bool,
        anchor: str | None,
        regions: bool,
        region_resolution: RegionResolution,
        low_volume_regions: bool,
        related_queries: bool,
    ) -> plans.Plan[list[TrendsRecord]]:
        cleaned = clean_terms(terms)
        chosen_anchor = ' '.join(anchor.split()) if anchor else cleaned[0]
        if not chosen_anchor:
            raise InvalidOptionError('anchor must be a non-empty search term')
        check_choice('region_resolution', region_resolution, constants.REGION_RESOLUTIONS)
        search = make_search(cleaned, geo, time_range, category, search_type, datetime.now(UTC).date())
        options = plans.ExploreOptions(separate, chosen_anchor, regions, region_resolution, low_volume_regions, related_queries)
        return plans.explore(search, options, self.language)

    def trending_now(self, geo: str, hours: int, limit: int | None) -> plans.Plan[list[TrendsRecord]]:
        code = make_search(('x',), geo, constants.DEFAULT_TIME_RANGE, 0, 'web', datetime.now(UTC).date()).geo
        if not code:
            raise InvalidOptionError('trending_now needs a country code such as "US"; Google lists no worldwide trends')
        check_number('hours', hours, constants.MIN_TRENDING_HOURS, constants.MAX_TRENDING_HOURS)
        if limit is not None:
            check_number('limit', limit, 1, MAX_TRENDS_PER_GEO)
        return plans.trending_now(code, hours, limit)

    def suggestions(self, text: str) -> plans.Plan[list[TrendsRecord]]:
        if not isinstance(text, str) or not text.strip():
            raise InvalidOptionError(f'text must be a non-empty search text, got {text!r}')
        return plans.suggestions(text.strip(), self.language)


class Trends:
    """Google Trends data: interest over time, by region and related queries for any number of terms on one scale,
    what is trending now, and topic suggestions.

    `language` is Google's hl code ("en-US"). `proxy` is an http(s) or socks proxy URL. `max_concurrency` caps the
    calls in flight; the pace Google tolerates from one IP still decides how fast they go.
    """

    def __init__(
        self, *, language: str = constants.DEFAULT_LANGUAGE, proxy: str | None = None, max_concurrency: int = DEFAULT_CONCURRENCY
    ) -> None:
        self._planner = _Planner(language)
        concurrency = check_number('max_concurrency', max_concurrency, 1, MAX_CONCURRENCY)
        self._transport = SyncTransport(self._planner.language, proxy, concurrency)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def close(self) -> None:
        self._transport.close()

    def explore(
        self,
        terms: Iterable[str] | str,
        *,
        geo: str = '',
        time_range: TimeRange = constants.DEFAULT_TIME_RANGE,
        category: int = 0,
        search_type: SearchType = 'web',
        separate: bool = False,
        anchor: str | None = None,
        regions: bool = True,
        region_resolution: RegionResolution = 'auto',
        low_volume_regions: bool = False,
        related_queries: bool = True,
    ) -> list[TrendsRecord]:
        """One record per term with its timeline, regions and related queries. All terms share one 0-100 scale; past
        five, comparisons are chained through `anchor` (the first term by default). `separate=True` scales each alone."""
        plan = self._planner.explore(
            terms,
            geo,
            time_range,
            category,
            search_type,
            separate,
            anchor,
            regions,
            region_resolution,
            low_volume_regions,
            related_queries,
        )
        return run_sync(plan, self._transport)

    def interest_over_time(
        self,
        terms: Iterable[str] | str,
        *,
        geo: str = '',
        time_range: TimeRange = constants.DEFAULT_TIME_RANGE,
        category: int = 0,
        search_type: SearchType = 'web',
        anchor: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """{term: timeline} on one shared scale, without the region and related-query calls, so it is the fastest call."""
        records = self.explore(
            terms,
            geo=geo,
            time_range=time_range,
            category=category,
            search_type=search_type,
            anchor=anchor,
            regions=False,
            related_queries=False,
        )
        return {record['term']: record['timeline'] for record in records}

    def trending_now(
        self, geo: str = 'US', *, hours: int = constants.DEFAULT_TRENDING_HOURS, limit: int | None = None
    ) -> list[TrendsRecord]:
        """What people search for right now, with volume, growth, categories and related searches.

        `hours` is how far back a trend may have started, from 1 to 191. Google lists at most the last 168 hours, so a
        larger value is read as 168."""
        return run_sync(self._planner.trending_now(geo, hours, limit), self._transport)

    def suggestions(self, text: str) -> list[TrendsRecord]:
        """Google's topics for a text, with the id ("/m/05z1_") that searches the topic instead of the words."""
        return run_sync(self._planner.suggestions(text), self._transport)


class AsyncTrends:
    """The asyncio version of Trends, with the same methods."""

    def __init__(
        self, *, language: str = constants.DEFAULT_LANGUAGE, proxy: str | None = None, max_concurrency: int = DEFAULT_CONCURRENCY
    ) -> None:
        self._planner = _Planner(language)
        concurrency = check_number('max_concurrency', max_concurrency, 1, MAX_CONCURRENCY)
        self._transport = AsyncTransport(self._planner.language, proxy, concurrency)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exception: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def explore(
        self,
        terms: Iterable[str] | str,
        *,
        geo: str = '',
        time_range: TimeRange = constants.DEFAULT_TIME_RANGE,
        category: int = 0,
        search_type: SearchType = 'web',
        separate: bool = False,
        anchor: str | None = None,
        regions: bool = True,
        region_resolution: RegionResolution = 'auto',
        low_volume_regions: bool = False,
        related_queries: bool = True,
    ) -> list[TrendsRecord]:
        plan = self._planner.explore(
            terms,
            geo,
            time_range,
            category,
            search_type,
            separate,
            anchor,
            regions,
            region_resolution,
            low_volume_regions,
            related_queries,
        )
        return await run_async(plan, self._transport)

    async def interest_over_time(
        self,
        terms: Iterable[str] | str,
        *,
        geo: str = '',
        time_range: TimeRange = constants.DEFAULT_TIME_RANGE,
        category: int = 0,
        search_type: SearchType = 'web',
        anchor: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        records = await self.explore(
            terms,
            geo=geo,
            time_range=time_range,
            category=category,
            search_type=search_type,
            anchor=anchor,
            regions=False,
            related_queries=False,
        )
        return {record['term']: record['timeline'] for record in records}

    async def trending_now(
        self, geo: str = 'US', *, hours: int = constants.DEFAULT_TRENDING_HOURS, limit: int | None = None
    ) -> list[TrendsRecord]:
        return await run_async(self._planner.trending_now(geo, hours, limit), self._transport)

    async def suggestions(self, text: str) -> list[TrendsRecord]:
        return await run_async(self._planner.suggestions(text), self._transport)
