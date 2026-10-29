"""Every error trendscale raises; all of them derive from TrendsError, so one except clause can catch them all."""

from __future__ import annotations


class TrendsError(Exception):
    """Base class of trendscale's errors."""


class InvalidOptionError(TrendsError, ValueError):
    """An argument cannot be used; the message names the argument and the value."""


class TrendsBlockedError(TrendsError):
    """Google kept refusing or rate-limiting the call. Wait a few minutes, make fewer calls at once, or use a proxy."""


class RequestRejectedError(TrendsError, ValueError):
    """Google answered 400: this request cannot succeed however often it is repeated."""


class UnreadableAnswerError(TrendsError, ValueError):
    """Google's answer is not the data the call should return; it may be a block page or a new format."""


class NoDataError(TrendsError):
    """Google has no chart for this search, such as a term nobody searches for in that place and period."""


class AnchorUnreadableError(TrendsError, ValueError):
    """The anchor term has no interest in one of the comparisons, so that comparison cannot be put on the shared scale."""
