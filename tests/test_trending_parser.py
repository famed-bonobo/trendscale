from datetime import UTC, datetime

import pytest

from trendscale._protocol import trending_parser as trending
from trendscale._protocol.trending_request import earliest_start, page_period_hours, trending_page_parameters

# The fixture is a capture of the page for the USA on 2026-11-12, cut down to five trends.
PAGE = 'trending_page_us'


def test_the_embedded_list_is_read_from_the_page(fixture_text):
    payload = trending.embedded_payload(fixture_text(PAGE))
    assert len(payload[1]) == 5


def test_a_page_without_the_trends_request_is_rejected():
    with pytest.raises(trending.UnreadableAnswerError, match=r'names no FeTrendingService\.ListTrends request'):
        trending.embedded_payload('<html>429</html>')


def test_a_page_without_the_data_of_the_request_is_rejected(fixture_text):
    page = fixture_text(PAGE).replace("key: 'ds:0'", "key: 'ds:7'")
    with pytest.raises(trending.UnreadableAnswerError, match='holds no data'):
        trending.embedded_payload(page)


def test_trends_are_ranked_in_googles_order_with_categories_and_related_searches(fixture_text):
    rows = trending.parse_trending(trending.embedded_payload(fixture_text(PAGE)), 'US')
    first = rows[0]
    assert first['rank'] == 1 and first['query'] == 'microsoft outage'
    assert first['startedAt'] == '2026-11-12T17:50:00Z' and first['isActive'] is True
    assert first['searchVolume'] == 5_000_000 and first['searchVolumeLabel'] == '5M+'
    assert first['volumeGrowthPercent'] == 1000
    assert first['relatedQueries'] == ['outlook outage', 'outlook', 'outlook down']
    assert first['categories'] == [{'id': 18, 'name': 'Technology'}]
    assert 'news' not in first
    assert [row['rank'] for row in rows] == [1, 2, 3, 4, 5]
    assert rows[4]['query'] == 'tornado watch' and rows[4]['endedAt'] == '2026-11-12T20:20:00Z'


def test_only_trends_that_started_in_the_hours_asked_for_are_kept_and_ranked(fixture_text):
    payload = trending.embedded_payload(fixture_text(PAGE))
    rows = trending.parse_trending(payload, 'US', datetime(2026, 11, 12, 17, 30, tzinfo=UTC))
    assert [(row['rank'], row['query']) for row in rows] == [
        (1, 'microsoft outage'),
        (2, 'czechia vs spain'),
        (3, 'tornado watch'),
    ]


def test_a_finished_trend_is_not_active():
    payload = [None, [['x', None, 'US', [1792177800], [1792203600], None, 500, None, 100, ['x'], [11], [], 'x']]]
    row = trending.parse_trending(payload, 'US')[0]
    assert row['isActive'] is False and row['endedAt'] == '2026-10-17T02:20:00Z'


def test_an_unexpected_layout_names_the_region():
    with pytest.raises(trending.UnreadableAnswerError, match='for GB has an unexpected layout'):
        trending.parse_trending([None, [['only one field']]], 'GB')


@pytest.mark.parametrize(
    ('searches', 'label'), [(100, '100+'), (500, '500+'), (1000, '1K+'), (20000, '20K+'), (2_000_000, '2M+')]
)
def test_volume_label_uses_googles_wording(searches, label):
    assert trending.volume_label(searches) == label


def test_explore_url_covers_the_trending_period():
    assert (
        trending.explore_url('norte fire', 'US', 24)
        == 'https://trends.google.com/trends/explore?q=norte+fire&date=now+1-d&geo=US'
    )
    assert trending.explore_url('x', 'GB', 4) == 'https://trends.google.com/trends/explore?q=x&date=now+4-H&geo=GB'


@pytest.mark.parametrize(
    ('hours', 'period'),
    [(1, 4), (4, 4), (5, 24), (24, 24), (25, 48), (48, 48), (100, 168), (168, 168), (191, 168)],
)
def test_the_page_period_is_the_shortest_that_covers_the_hours(hours, period):
    assert page_period_hours(hours) == period
    assert trending_page_parameters('CR', hours, 'es-419') == {'geo': 'CR', 'hl': 'es-419', 'hours': str(period)}


def test_a_period_the_page_offers_needs_no_cut():
    now = datetime(2026, 11, 13, tzinfo=UTC)
    assert earliest_start(24, now) is None and earliest_start(168, now) is None
    assert earliest_start(6, now) == datetime(2026, 11, 12, 18, tzinfo=UTC)
