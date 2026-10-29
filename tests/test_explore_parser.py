import pytest

from trendscale._protocol import explore_parser as parser


def test_strip_guard_returns_the_json_after_the_guard_line(fixture_text):
    assert 'widgets' in parser.strip_guard(fixture_text('explore_one'))


def test_strip_guard_rejects_an_answer_without_the_guard():
    with pytest.raises(parser.UnreadableAnswerError, match='does not start with'):
        parser.strip_guard('<html>Error 429</html>')


def test_strip_guard_rejects_json_that_does_not_parse():
    with pytest.raises(parser.UnreadableAnswerError, match='not JSON'):
        parser.strip_guard(")]}'\n{broken")


def test_weekly_timeline_has_iso_dates_and_marks_the_partial_last_week(fixture_text):
    data = parser.strip_guard(fixture_text('explore_one__TIMESERIES'))
    granularity, series = parser.parse_timeline(data, 'WEEK', 1)
    assert granularity == 'week'
    assert len(series) == 1 and len(series[0]) == 53
    assert series[0][0] == {'date': '2025-10-12', 'timestamp': 1760227200, 'value': 58, 'hasData': True, 'isPartial': False}
    assert series[0][-1]['isPartial'] is True


def test_hourly_timeline_dates_carry_a_time_of_day(fixture_text):
    data = parser.strip_guard(fixture_text('explore_hourly__TIMESERIES'))
    _, series = parser.parse_timeline(data, 'EIGHT_MINUTE', 1)
    assert series[0][0]['date'] == '2026-10-16T06:40:00Z'


def test_two_term_timeline_splits_one_series_per_term(fixture_text):
    data = parser.strip_guard(fixture_text('explore_two__TIMESERIES'))
    _, series = parser.parse_timeline(data, 'WEEK', 2)
    assert len(series) == 2 and len(series[0]) == len(series[1]) == 261


def test_summary_leaves_the_partial_last_point_out_of_the_average(fixture_text):
    data = parser.strip_guard(fixture_text('explore_one__TIMESERIES'))
    _, series = parser.parse_timeline(data, 'WEEK', 1)
    summary = parser.timeline_summary(series[0])
    assert summary == {'average': 62.2, 'peakValue': 100, 'peakDate': '2026-06-14', 'latestValue': 36}


def test_summary_of_an_empty_timeline_is_empty():
    assert parser.timeline_summary([]) == {'average': None, 'peakValue': None, 'peakDate': None, 'latestValue': None}


def test_regions_are_sorted_highest_first(fixture_text):
    data = parser.strip_guard(fixture_text('explore_one__GEO_MAP'))
    regions = parser.parse_regions(data, 1)[0]
    assert regions[0]['geoCode'] == 'US-WY' and regions[0]['value'] == 100
    assert [region['value'] for region in regions] == sorted((region['value'] for region in regions), reverse=True)


def test_compared_regions_hold_a_separate_list_per_term(fixture_text):
    data = parser.strip_guard(fixture_text('explore_two__GEO_MAP'))
    first, second = parser.parse_regions(data, 2)
    assert first[0]['geoName'] == 'China' and second[0]['geoName'] == 'Nigeria'


def test_market_areas_have_a_code_and_no_coordinates(fixture_text):
    data = parser.strip_guard(fixture_text('geo_DMA'))
    area = parser.parse_regions(data, 1)[0][0]
    assert area['geoCode'] == '759' and area['latitude'] is None


def test_related_queries_flag_breakout_growth_and_link_to_trends(fixture_text):
    data = parser.strip_guard(fixture_text('explore_one__RELATED_QUERIES'))
    related = parser.parse_related_queries(data)
    assert related['top'][0]['query'] == 'what is python'
    assert related['top'][0]['trendsUrl'].startswith('https://trends.google.com/trends/explore?q=what+is+python')
    assert related['rising'][0]['isBreakout'] is True


def test_suggestions_are_ranked_topics_with_ids(fixture_text):
    suggestions = parser.parse_suggestions(parser.strip_guard(fixture_text('autocomplete_python')))
    assert suggestions[0] == {'rank': 1, 'topicId': '/m/05z1_', 'title': 'Python', 'kind': 'Programming language'}
    assert len(suggestions) == 5
