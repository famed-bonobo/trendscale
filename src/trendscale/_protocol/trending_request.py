"""Builds the request for Google Trends' "Trending now" page and tells which of its trends fall in the hours asked for.

The page lists the trends that started within one of four periods. Any other number of hours is served from the
shortest period that covers it, keeping the trends that started within those hours.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from . import constants as config


def page_period_hours(hours: int) -> int:
    """The shortest period the page offers that covers the hours asked for, or its longest when none does."""
    periods = config.TRENDING_PAGE_PERIODS_HOURS
    return next((period for period in periods if period >= hours), periods[-1])


def trending_page_parameters(geo: str, hours: int, language: str) -> dict[str, str]:
    return {'geo': geo, 'hl': language, 'hours': str(page_period_hours(hours))}


def earliest_start(hours: int, now: datetime) -> datetime | None:
    """The time a trend must have started by to count, or None when the page's own period already is the answer."""
    if hours >= page_period_hours(hours):
        return None
    return now - timedelta(hours=hours)
