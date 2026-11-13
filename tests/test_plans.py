"""Plans driven by both runners over a fake transport: one comparison, anchored chains past five terms, trending now."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from trendscale import NoDataError, TrendsBlockedError, plans
from trendscale._protocol.explore_parser import strip_guard
from trendscale._protocol.trending_parser import embedded_payload
from trendscale.options import make_search
from trendscale.runner import run_async, run_sync

TODAY = date(2026, 10, 29)
OPTIONS = plans.ExploreOptions(
    separate=False,
    anchor='python',
    include_regions=True,
    region_resolution='auto',
    include_low_volume_regions=False,
    include_related_queries=True,
)


class FakeTransport:
    """Answers explore calls with `explore(terms)` and chart calls with `chart(endpoint, request)`."""

    max_concurrency = 3

    def __init__(self, explore: Any, chart: Any) -> None:
        self.explore, self.chart = explore, chart
        self.urls: list[str] = []

    def get_json(self, url: str, params: dict[str, str]) -> Any:
        self.urls.append(url)
        request = json.loads(params['req'])
        if url.endswith('/explore'):
            return self.explore([item['keyword'] for item in request['comparisonItem']])
        return self.chart(url.rsplit('/', 1)[1], request)

    def trending(self, geo: str, hours: int) -> Any:
        raise AssertionError('not used')


class AsyncFakeTransport(FakeTransport):
    async def get_json(self, url: str, params: dict[str, str]) -> Any:  # type: ignore[override]
        return FakeTransport.get_json(self, url, params)


class TrendingTransport:
    """Answers every trending call with one list of trends and keeps the region and hours each call asked for."""

    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.asked: list[tuple[str, int]] = []

    def trending(self, geo: str, hours: int) -> Any:
        self.asked.append((geo, hours))
        return self.payload


def trend_started(query: str, hours_ago: int) -> list[Any]:
    """One trend of the list as Google lays it out, started that many hours before now."""
    started = int((datetime.now(UTC) - timedelta(hours=hours_ago)).timestamp())
    return [query, None, 'BR', [started], None, None, 500, None, 100, [query], [11], [], query]


def recorded(fixture_text: Any) -> FakeTransport:
    """Google's real answers for "python" and "javascript" over five years."""
    charts = {
        'multiline': 'explore_two__TIMESERIES',
        'comparedgeo': 'explore_two__GEO_MAP',
        'relatedsearches': 'explore_two__RELATED_QUERIES_0',
    }
    return FakeTransport(
        lambda _terms: strip_guard(fixture_text('explore_two')),
        lambda endpoint, _request: strip_guard(fixture_text(charts[endpoint])),
    )


def synthetic(values_by_term: dict[str, list[int]]) -> FakeTransport:
    """Explore answers for any group of terms, whose timeline holds each term's values scaled so the group peaks at 100."""

    def explore(terms: list[str]) -> dict[str, Any]:
        return {'widgets': [{'id': 'TIMESERIES', 'token': 't', 'request': {'resolution': 'WEEK', 'terms': terms}}]}

    def chart(_endpoint: str, request: dict[str, Any]) -> dict[str, Any]:
        terms = request['terms']
        top = max(max(values_by_term[term]) for term in terms)
        rows = [
            {
                'time': str(1760227200 + week * 604800),
                'value': [round(values_by_term[term][week] * 100 / top) for term in terms],
                'hasData': [True] * len(terms),
            }
            for week in range(len(values_by_term[terms[0]]))
        ]
        return {'default': {'timelineData': rows}}

    return FakeTransport(explore, chart)


@pytest.mark.parametrize('runner', ['sync', 'async'])
async def test_two_terms_share_one_comparison(fixture_text: Any, runner: str) -> None:
    transport = recorded(fixture_text)
    search = make_search(('python', 'javascript'), '', 'past_5_years', 0, 'web', TODAY)
    records = await _run(runner, plans.explore(search, OPTIONS, 'en-US'), transport)
    assert [record['term'] for record in records] == ['python', 'javascript']
    assert records[0]['comparison'] == 'together' and records[0]['comparedWith'] == ['javascript']
    assert records[0]['granularity'] == 'week' and len(records[0]['timeline']) == len(records[1]['timeline'])
    assert records[0]['regions'] and records[0]['relatedQueries']['top']
    # One explore call, then the timeline, the regions and each term's related queries together.
    assert len(transport.urls) == 5


def test_more_than_five_terms_are_chained_onto_one_scale() -> None:
    popularity = {'python': [50, 60], 'a': [100, 80], 'b': [10, 20], 'c': [5, 5], 'd': [40, 40], 'e': [200, 100], 'f': [25, 50]}
    search = make_search(tuple(popularity), 'US', 'past_12_months', 0, 'web', TODAY)
    records = run_sync(plans.explore(search, OPTIONS, 'en-US'), synthetic(popularity))  # type: ignore[arg-type]
    values = {record['term']: [point['value'] for point in record['timeline']] for record in records}
    assert records[0]['comparison'] == 'anchored' and records[0]['anchor']['term'] == 'python'
    # "e" peaks highest of all, in the second group, and still lands at 100 on the shared scale.
    assert values['e'][0] == 100
    assert values['a'][0] == pytest.approx(50, abs=1) and values['python'][0] == pytest.approx(25, abs=1)


def test_separate_terms_are_each_scaled_alone() -> None:
    popularity = {'python': [50, 60], 'snake': [5, 10]}
    search = make_search(tuple(popularity), '', 'past_12_months', 0, 'web', TODAY)
    options = plans.ExploreOptions(True, 'python', False, 'auto', False, False)
    records = run_sync(plans.explore(search, options, 'en-US'), synthetic(popularity))  # type: ignore[arg-type]
    assert [max(point['value'] for point in record['timeline']) for record in records] == [100, 100]
    assert records[1]['comparison'] == 'separate' and records[1]['comparedWith'] == []


def test_a_search_without_a_timeline_names_the_terms() -> None:
    transport = FakeTransport(lambda _terms: {'widgets': []}, lambda *_: None)
    search = make_search(('qwzx',), 'CR', 'past_7_days', 0, 'web', TODAY)
    with pytest.raises(NoDataError, match='qwzx'):
        run_sync(plans.explore(search, OPTIONS, 'en-US'), transport)  # type: ignore[arg-type]


def test_a_blocked_chart_fails_the_search() -> None:
    def blocked(_endpoint: str, _request: dict[str, Any]) -> Any:
        raise TrendsBlockedError('every attempt was refused')

    transport = FakeTransport(
        lambda terms: {'widgets': [{'id': 'TIMESERIES', 'token': 't', 'request': {'resolution': 'WEEK'}}]}, blocked
    )
    search = make_search(('python',), '', 'past_12_months', 0, 'web', TODAY)
    with pytest.raises(TrendsBlockedError):
        run_sync(plans.explore(search, OPTIONS, 'en-US'), transport)  # type: ignore[arg-type]


def test_trending_now_ranks_the_listed_trends_and_tells_their_period(fixture_text: Any) -> None:
    transport = TrendingTransport(embedded_payload(fixture_text('trending_page_us')))
    rows = run_sync(plans.trending_now('US', 24, 3), transport)  # type: ignore[arg-type]
    assert transport.asked == [('US', 24)]
    assert [(row['rank'], row['query']) for row in rows] == [
        (1, 'microsoft outage'),
        (2, 'italy vs france'),
        (3, 'czechia vs spain'),
    ]
    assert rows[0]['hours'] == 24 and rows[0]['scrapedAt']
    assert rows[0]['trendsUrl'] == 'https://trends.google.com/trends/explore?q=microsoft+outage&date=now+1-d&geo=US'


def test_trending_now_keeps_the_trends_that_started_within_hours_between_two_periods() -> None:
    transport = TrendingTransport([None, [trend_started('older', 10), trend_started('newer', 1)]])
    rows = run_sync(plans.trending_now('BR', 6, None), transport)  # type: ignore[arg-type]
    assert [(row['rank'], row['query'], row['hours']) for row in rows] == [(1, 'newer', 6)]


def test_trending_now_reads_more_hours_than_google_lists_as_its_longest_period() -> None:
    transport = TrendingTransport([None, [trend_started('older', 150), trend_started('newer', 1)]])
    rows = run_sync(plans.trending_now('BR', 191, None), transport)  # type: ignore[arg-type]
    assert transport.asked == [('BR', 168)]
    assert [row['query'] for row in rows] == ['older', 'newer']
    assert rows[0]['hours'] == 168 and rows[0]['trendsUrl'].endswith('date=now+7-d&geo=BR')


async def _run(runner: str, plan: plans.Plan[Any], transport: FakeTransport) -> Any:
    if runner == 'sync':
        return run_sync(plan, transport)  # type: ignore[arg-type]
    async_transport = AsyncFakeTransport(transport.explore, transport.chart)
    result = await run_async(plan, async_transport)  # type: ignore[arg-type]
    transport.urls = async_transport.urls
    return result
