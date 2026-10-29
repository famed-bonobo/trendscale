import json

from trendscale._protocol import explore_parser, explore_request


def test_explore_parameters_name_every_term_with_its_region_and_period():
    parameters = explore_request.explore_parameters(['a', 'b'], 'US', 'today 12-m', 0, '', 'en-US')
    request = json.loads(parameters['req'])
    assert [item['keyword'] for item in request['comparisonItem']] == ['a', 'b']
    assert request['comparisonItem'][0] == {'keyword': 'a', 'geo': 'US', 'time': 'today 12-m'}
    assert parameters['tz'] == '0' and parameters['hl'] == 'en-US'


def test_one_term_answer_has_plain_widget_ids(fixture_text):
    widgets = explore_request.read_widgets(explore_parser.strip_guard(fixture_text('explore_one'))['widgets'])
    assert widgets.timeline is not None and widgets.regions is not None
    assert list(widgets.related_queries) == [0]


def test_several_terms_have_one_related_widget_each_and_one_shared_regions_widget(fixture_text):
    widgets = explore_request.read_widgets(explore_parser.strip_guard(fixture_text('explore_two'))['widgets'])
    assert widgets.regions['id'] == 'GEO_MAP'
    assert sorted(widgets.related_queries) == [0, 1]


def test_widget_urls_follow_the_chart_kind(fixture_text):
    widgets = explore_request.read_widgets(explore_parser.strip_guard(fixture_text('explore_one'))['widgets'])
    assert explore_request.widget_url(widgets.timeline).endswith('/multiline')
    assert explore_request.widget_url(widgets.regions).endswith('/comparedgeo')
    assert explore_request.widget_url(widgets.related_queries[0]).endswith('/relatedsearches')


def test_region_resolution_is_applied_only_to_the_regions_chart(fixture_text):
    widgets = explore_request.read_widgets(explore_parser.strip_guard(fixture_text('explore_one'))['widgets'])
    regions = json.loads(explore_request.widget_parameters(widgets.regions, 'en-US', 'dma', True)['req'])
    timeline = json.loads(explore_request.widget_parameters(widgets.timeline, 'en-US', 'dma', True)['req'])
    assert regions['resolution'] == 'DMA' and regions['includeLowSearchVolumeGeos'] is True
    assert 'includeLowSearchVolumeGeos' not in timeline


def test_auto_region_resolution_keeps_googles_choice(fixture_text):
    widgets = explore_request.read_widgets(explore_parser.strip_guard(fixture_text('explore_one'))['widgets'])
    regions = json.loads(explore_request.widget_parameters(widgets.regions, 'en-US', 'auto', False)['req'])
    assert regions['resolution'] == 'REGION'


def test_trends_page_url_reproduces_the_comparison():
    url = explore_request.trends_page_url(['python', 'java'], 'US-CA', 'today 5-y', 31, 'youtube')
    assert url == 'https://trends.google.com/trends/explore?q=python%2Cjava&date=today+5-y&geo=US-CA&cat=31&gprop=youtube'


def test_trends_page_url_leaves_out_empty_options():
    assert (
        explore_request.trends_page_url(['python'], '', 'all', 0, '')
        == 'https://trends.google.com/trends/explore?q=python&date=all'
    )
