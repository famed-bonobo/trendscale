"""The pytrends-compatible TrendReq: the same calls return pytrends' pandas tables, built from trendscale records."""

from __future__ import annotations

from typing import Any

import pytest

pandas = pytest.importorskip('pandas')

from trendscale import InvalidOptionError  # noqa: E402
from trendscale.pytrends import TrendReq  # noqa: E402


def record(term: str, values: list[int], regions: list[tuple[str, str, int]] | None = None) -> dict[str, Any]:
    timeline = [
        {
            'date': f'2026-10-{day:02d}',
            'timestamp': 1793000000 + day * 86400,
            'value': value,
            'hasData': True,
            'isPartial': day == len(values),
        }
        for day, value in enumerate(values, 1)
    ]
    return {
        'term': term,
        'timeline': timeline,
        'regions': [{'geoName': name, 'geoCode': code, 'value': value} for name, code, value in regions or []],
        'relatedQueries': {'top': [{'query': f'{term} tutorial', 'value': 100}], 'rising': []},
    }


@pytest.fixture
def pytrends(monkeypatch: pytest.MonkeyPatch) -> TrendReq:
    client = TrendReq(hl='en-US', tz=360)
    calls: list[dict[str, Any]] = []

    def explore(terms: list[str], **options: Any) -> list[dict[str, Any]]:
        calls.append({'terms': terms, **options})
        return [record(term, [10 * (index + 1), 20], [('Texas', 'US-TX', 50 + index)]) for index, term in enumerate(terms)]

    monkeypatch.setattr(client._trends, 'explore', explore)
    client.calls = calls  # type: ignore[attr-defined]
    return client


def test_interest_over_time_matches_pytrends_shape(pytrends: TrendReq) -> None:
    terms = ['python', 'javascript', 'rust', 'go', 'java', 'kotlin']
    pytrends.build_payload(terms, timeframe='today 5-y', geo='US', gprop='youtube')
    frame = pytrends.interest_over_time()
    assert list(frame.columns) == [*terms, 'isPartial']
    assert frame.index.name == 'date' and str(frame.index.dtype).startswith('datetime64')
    assert frame['isPartial'].tolist() == [False, True]
    assert pytrends.calls[0]['search_type'] == 'youtube' and pytrends.calls[0]['time_range'] == 'today 5-y'  # type: ignore[attr-defined]


def test_interest_by_region_and_related_queries(pytrends: TrendReq) -> None:
    pytrends.build_payload(['python', 'javascript'])
    regions = pytrends.interest_by_region(resolution='REGION', inc_geo_code=True)
    assert list(regions.columns) == ['geoCode', 'python', 'javascript'] and regions.loc['Texas', 'javascript'] == 51
    assert pytrends.calls[0]['region_resolution'] == 'region'  # type: ignore[attr-defined]
    related = pytrends.related_queries()
    assert related['python']['top']['query'].tolist() == ['python tutorial'] and related['python']['rising'] is None


def test_refusals_name_the_problem(pytrends: TrendReq) -> None:
    with pytest.raises(InvalidOptionError, match='build_payload'):
        pytrends.interest_over_time()
    pytrends.build_payload(['a', 'b', 'c', 'd', 'e', 'f'])
    with pytest.raises(InvalidOptionError, match='at most 5 terms'):
        pytrends.interest_by_region()
    with pytest.raises(InvalidOptionError, match='gprop must be one of'):
        pytrends.build_payload(['a'], gprop='videos')
