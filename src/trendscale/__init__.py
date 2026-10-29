"""Google Trends for Python: any number of terms on one 0-100 scale, regions, related queries, trending now.

    from trendscale import Trends

    with Trends() as trends:
        timelines = trends.interest_over_time(["python", "javascript", "rust", "go", "java", "kotlin", "swift"], geo="US")

Moving from pytrends? `from trendscale.pytrends import TrendReq` takes the same calls, without the five-term limit.
"""

from .client import AsyncTrends, Trends
from .errors import (
    AnchorUnreadableError,
    InvalidOptionError,
    NoDataError,
    RequestRejectedError,
    TrendsBlockedError,
    TrendsError,
    UnreadableAnswerError,
)

__version__ = '0.1.0'
__all__ = [
    'AnchorUnreadableError',
    'AsyncTrends',
    'InvalidOptionError',
    'NoDataError',
    'RequestRejectedError',
    'Trends',
    'TrendsBlockedError',
    'TrendsError',
    'UnreadableAnswerError',
    '__version__',
]
