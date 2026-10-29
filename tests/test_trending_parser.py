import json

import pytest

from trendscale._protocol import trending_parser as trending
from trendscale._protocol.trending_request import trending_form


def test_batch_payload_unwraps_the_rpc_entry(fixture_text):
    payload = trending.batch_payload(fixture_text('gb_4h'), 'i0OFE')
    assert len(payload[1]) == 24


def test_batch_payload_rejects_an_answer_without_the_guard():
    with pytest.raises(trending.UnreadableAnswerError, match='does not start with'):
        trending.batch_payload('<html>429</html>', 'i0OFE')


def test_batch_payload_rejects_an_answer_without_the_rpc(fixture_text):
    with pytest.raises(trending.UnreadableAnswerError, match='no w4opAf entry'):
        trending.batch_payload(fixture_text('gb_4h'), 'w4opAf')


def test_trends_are_ranked_in_googles_order_with_categories_and_related_searches(fixture_text):
    rows = trending.parse_trending(trending.batch_payload(fixture_text('gb_4h'), 'i0OFE'), 'GB')
    first = rows[0]
    assert first['rank'] == 1 and first['query'] == 'australia vs new zealand'
    assert first['startedAt'] == '2026-10-17T04:50:00Z' and first['isActive'] is True
    assert first['searchVolume'] == 2000 and first['searchVolumeLabel'] == '2K+'
    assert first['volumeGrowthPercent'] == 1000
    assert first['relatedQueries'] == ['all blacks']
    assert first['categories'] == [{'id': 17, 'name': 'Sports'}, {'id': 4, 'name': 'Entertainment'}]
    assert 'news' not in first
    assert [row['rank'] for row in rows] == list(range(1, 25))


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


def test_form_asks_for_region_language_and_hours_without_news():
    form = trending_form('CR', 24, 'es-419')
    envelope = json.loads(form['f.req'])
    rpc_id, arguments = envelope[0][0][0], json.loads(envelope[0][0][1])
    assert rpc_id == 'i0OFE'
    assert arguments == [None, None, 'CR', 0, 'es', 24, 1]
