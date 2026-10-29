"""What a caller asks Google Trends for, validated before any call is sent: terms, place, period and search type.

Periods can be given as a preset name ("past_12_months"), as Google's own code ("today 5-y", "now 7-d", the format
pytrends takes), as two dates ("2024-01-01 2024-06-30" or a pair of dates), or hour by hour ("2026-10-20T08 2026-10-21T20").
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from ._protocol import constants
from .errors import InvalidOptionError

SearchType = Literal['web', 'images', 'news', 'youtube', 'shopping']
RegionResolution = Literal['auto', 'country', 'region', 'city', 'dma']
GEO_PATTERN = re.compile(r'^[A-Z]{2}(-[A-Z0-9]{1,3}(-[0-9]{1,4})?)?$')
LANGUAGE_PATTERN = re.compile(r'^[a-z]{2,3}(-[A-Za-z]{2,4})?$')
GOOGLE_PERIOD_PATTERN = re.compile(r'^(now \d+-[Hd]|today \d+-[dmy]|all)$')
DAY_RANGE_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2}) (\d{4}-\d{2}-\d{2})$')
HOUR_RANGE_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}) (\d{4}-\d{2}-\d{2}T\d{2})$')
FIRST_DAY_OF_DATA = date(2004, 1, 1)
# Google serves hour-by-hour data for at most the last 7 days, so a custom hourly range cannot be longer.
MAX_HOURLY_RANGE = timedelta(days=7)
MAX_CATEGORY = 10_000


@dataclass(frozen=True)
class Search:
    """One explore search: terms in a place over a period; Google compares at most five terms in one call."""

    terms: tuple[str, ...]
    geo: str
    time_range: str
    category: int
    search_property: str


def clean_terms(terms: Iterable[str] | str) -> tuple[str, ...]:
    """The terms with spaces tidied and repeats removed, in the order given; a single text is one term."""
    values = [terms] if isinstance(terms, str) else list(terms)
    if not values:
        raise InvalidOptionError('terms must name at least one search term, such as ["python", "javascript"]')
    if any(not isinstance(term, str) or not term.strip() for term in values):
        raise InvalidOptionError(f'terms must be non-empty texts, got {values!r}')
    cleaned = tuple(dict.fromkeys(' '.join(term.split()) for term in values))
    too_long = [term for term in cleaned if len(term) > constants.MAX_TERM_LENGTH]
    if too_long:
        raise InvalidOptionError(f'terms longer than {constants.MAX_TERM_LENGTH} characters: {too_long[0][:40]!r}...')
    if len(cleaned) > constants.MAX_TERMS:
        raise InvalidOptionError(f'{len(cleaned)} terms is more than the {constants.MAX_TERMS} one comparison can take')
    return cleaned


def make_search(
    terms: tuple[str, ...], geo: str, time_range: str | tuple[date, date], category: int, search_type: str, today: date
) -> Search:
    code = geo.strip().upper() if isinstance(geo, str) else geo
    if not isinstance(code, str) or (code and not GEO_PATTERN.match(code)):
        raise InvalidOptionError(f'geo must be "" for the whole world or a code such as "US", "US-CA" or "GB-ENG", got {geo!r}')
    check_number('category', category, 0, MAX_CATEGORY)
    check_choice('search_type', search_type, constants.SEARCH_PROPERTIES)
    return Search(terms, code, period_code(time_range, today), category, constants.SEARCH_PROPERTIES[search_type])


def period_code(time_range: str | tuple[date, date], today: date) -> str:
    """Google's code for a period, from any of the forms this module accepts."""
    if isinstance(time_range, tuple):
        if len(time_range) != 2 or not all(isinstance(day, date) for day in time_range):
            raise InvalidOptionError(f'time_range as a tuple must be (start date, end date), got {time_range!r}')
        time_range = f'{time_range[0].isoformat()} {time_range[1].isoformat()}'
    if not isinstance(time_range, str):
        raise InvalidOptionError(f'time_range must be a text or a pair of dates, got {time_range!r}')
    text = ' '.join(time_range.split())
    if text in constants.TIME_RANGE_PRESETS:
        return constants.TIME_RANGE_PRESETS[text]
    if GOOGLE_PERIOD_PATTERN.match(text):
        return text
    if DAY_RANGE_PATTERN.match(text) or HOUR_RANGE_PATTERN.match(text):
        return _checked_custom_range(text, today)
    raise InvalidOptionError(
        f'time_range must be one of {list(constants.TIME_RANGE_PRESETS)}, a Google code such as "today 5-y" or "now 7-d", '
        f'or two dates such as "2024-01-01 2024-06-30"; got {time_range!r}'
    )


def check_language(language: str) -> str:
    if not isinstance(language, str) or not LANGUAGE_PATTERN.match(language):
        raise InvalidOptionError(f'language must be a code such as "en-US" or "es", got {language!r}')
    return language


def check_number(name: str, value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InvalidOptionError(f'{name} must be a whole number from {minimum} to {maximum}, got {value!r}')
    return value


def check_choice(name: str, value: object, choices: Iterable[str]) -> str:
    options = list(choices)
    if value not in options:
        raise InvalidOptionError(f'{name} must be one of {options}, got {value!r}')
    return str(value)


def _checked_custom_range(text: str, today: date) -> str:
    hourly = HOUR_RANGE_PATTERN.match(text)
    pattern = '%Y-%m-%dT%H' if hourly else '%Y-%m-%d'
    try:
        start, end = (datetime.strptime(part, pattern) for part in text.split(' '))
    except ValueError as error:
        raise InvalidOptionError(f'time_range has an impossible date: {text!r}') from error
    if end < start:
        raise InvalidOptionError(f'time_range ends before it starts: {text!r}')
    if start.date() < FIRST_DAY_OF_DATA or end.date() > today:
        raise InvalidOptionError(
            f'time_range must lie between {FIRST_DAY_OF_DATA.isoformat()} and today ({today.isoformat()}), got {text!r}'
        )
    if hourly and end - start > MAX_HOURLY_RANGE:
        raise InvalidOptionError(f'An hour-by-hour time_range can cover at most 7 days, got {text!r}')
    return text
