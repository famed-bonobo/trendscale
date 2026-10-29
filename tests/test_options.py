"""Argument validation: periods in every accepted form, places, terms, and the refusals that name the argument."""

from __future__ import annotations

from datetime import date

import pytest

from trendscale import InvalidOptionError
from trendscale.options import clean_terms, make_search, period_code

TODAY = date(2026, 10, 29)


@pytest.mark.parametrize(
    ('given', 'code'),
    [
        ('past_12_months', 'today 12-m'),
        ('past_7_days', 'now 7-d'),
        ('since_2004', 'all'),
        ('today 5-y', 'today 5-y'),
        ('now  1-H', 'now 1-H'),
        ('2024-01-01 2024-06-30', '2024-01-01 2024-06-30'),
        ('2026-10-20T08 2026-10-21T20', '2026-10-20T08 2026-10-21T20'),
        ((date(2025, 1, 1), date(2025, 12, 31)), '2025-01-01 2025-12-31'),
    ],
)
def test_periods_in_every_form(given: object, code: str) -> None:
    assert period_code(given, TODAY) == code  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ('given', 'message'),
    [
        ('last year', 'time_range must be one of'),
        ('2024-06-30 2024-01-01', 'ends before it starts'),
        ('2003-01-01 2004-06-30', 'must lie between'),
        ('2026-10-01T00 2026-10-20T00', 'at most 7 days'),
        ('2024-02-30 2024-03-01', 'impossible date'),
    ],
)
def test_bad_periods_are_refused(given: str, message: str) -> None:
    with pytest.raises(InvalidOptionError, match=message):
        period_code(given, TODAY)


def test_terms_are_tidied_and_deduplicated() -> None:
    assert clean_terms(['  machine   learning ', 'python', 'machine learning']) == ('machine learning', 'python')
    assert clean_terms('python') == ('python',)


@pytest.mark.parametrize('terms', [[], [''], ['ok', 3], ['x' * 101]])
def test_bad_terms_are_refused(terms: list[object]) -> None:
    with pytest.raises(InvalidOptionError):
        clean_terms(terms)  # type: ignore[arg-type]


def test_places_search_types_and_categories() -> None:
    search = make_search(('python',), 'us-ca', 'past_90_days', 13, 'youtube', TODAY)
    assert search.geo == 'US-CA' and search.search_property == 'youtube' and search.category == 13
    with pytest.raises(InvalidOptionError, match='geo must be'):
        make_search(('python',), 'United States', 'past_90_days', 0, 'web', TODAY)
    with pytest.raises(InvalidOptionError, match='search_type must be one of'):
        make_search(('python',), '', 'past_90_days', 0, 'video', TODAY)
