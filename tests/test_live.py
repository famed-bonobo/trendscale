"""Every public method against Google itself, to catch a change in Google's answers. Run with: pytest -m live"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from trendscale import AsyncTrends, Trends

pytestmark = pytest.mark.live
ASSISTANTS = ['chatgpt', 'gemini', 'claude', 'perplexity', 'copilot', 'deepseek', 'grok']


@pytest.fixture(scope='module')
def trends() -> Iterator[Trends]:
    with Trends() as client:
        yield client


def test_two_terms_with_regions_and_related_queries(trends: Trends) -> None:
    records = trends.explore(['python', 'javascript'], geo='US')
    assert [record['term'] for record in records] == ['python', 'javascript']
    assert all(len(record['timeline']) >= 50 for record in records)
    assert records[0]['regions'] and records[0]['relatedQueries']['top']
    assert max(point['value'] for record in records for point in record['timeline']) == 100


def test_seven_terms_on_one_scale(trends: Trends) -> None:
    timelines = trends.interest_over_time(ASSISTANTS, geo='US', time_range='past_12_months')
    assert list(timelines) == ASSISTANTS
    assert max(point['value'] for timeline in timelines.values() for point in timeline) == 100
    assert len({len(timeline) for timeline in timelines.values()}) == 1


def test_trending_now(trends: Trends) -> None:
    rows = trends.trending_now('US', limit=10)
    assert len(rows) == 10 and rows[0]['rank'] == 1 and rows[0]['searchVolume']


def test_suggestions(trends: Trends) -> None:
    topics = trends.suggestions('python')
    assert any(topic['topicId'] == '/m/05z1_' for topic in topics)


async def test_async_explore() -> None:
    async with AsyncTrends() as client:
        records = await client.explore(['rust', 'go'], time_range='past_90_days', regions=False, related_queries=False)
    assert len(records) == 2 and records[0]['granularity'] == 'day'
