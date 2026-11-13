"""Constants of trendscale: Google's internal endpoints, the codes they take and the limits measured.

The calls follow what trends.google.com's own page sends (checked against live answers on 2026-10-17): an explore call
returns one widget per chart with a token, and each chart's data is fetched with its widget's request and token.
"""

ORIGIN = 'https://trends.google.com'
LANDING_URL = f'{ORIGIN}/trends/explore'
EXPLORE_URL = f'{ORIGIN}/trends/api/explore'
WIDGET_DATA_URL = f'{ORIGIN}/trends/api/widgetdata'
AUTOCOMPLETE_URL = f'{ORIGIN}/trends/api/autocomplete'
GEO_PICKER_URL = f'{ORIGIN}/trends/api/explore/pickers/geo'
TRENDING_PAGE_URL = f'{ORIGIN}/trending'
# Every answer of the /trends/api endpoints starts with this guard line, which is not JSON.
RESPONSE_GUARD = ")]}'"

# Widget ids in an explore answer and the data endpoint each one is read from.
TIMELINE_WIDGET = 'TIMESERIES'
REGIONS_WIDGET = 'GEO_MAP'
RELATED_QUERIES_WIDGET = 'RELATED_QUERIES'
WIDGET_ENDPOINTS = {
    TIMELINE_WIDGET: 'multiline',
    REGIONS_WIDGET: 'comparedgeo',
    RELATED_QUERIES_WIDGET: 'relatedsearches',
}

# The "Trending now" page embeds its list as the data of this service request. The batch RPC that returned the list
# before (i0OFE) answers status 7, permission denied, from every IP since November 2026 (seen 2026-11-12).
TRENDING_SERVICE = 'FeTrendingService.ListTrends'
# Periods the page offers, in hours; with any other value of its "hours" parameter it shows the last 24.
TRENDING_PAGE_PERIODS_HOURS = (4, 24, 48, 168)

# A comparison holds at most this many terms on one 0-100 scale.
MAX_TERMS_PER_COMPARISON = 5
# Google answers 429 to a cookie-less first call and sets the NID cookie with it; the next call carries it.
COOKIE_NAME = 'NID'

DEFAULT_LANGUAGE = 'en-US'
# Times in the answers are UTC epoch seconds when the request names UTC (offset 0).
UTC_OFFSET_MINUTES = 0

REQUEST_TIMEOUT_SECONDS = 30
ATTEMPT_DEADLINE_SECONDS = 25
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
}

# Requests per second from each IP, adjusted while running. Measured 2026-10-17: Apify's datacenter proxy answered 500
# of 500 calls at 12 a second spread over its IPs, while one IP at about 10 a second began to get 429 after some 350
# calls, and a home IP that had made about 400 calls in a few minutes was refused for 31 to 62 seconds.
IP_RATE_INITIAL = 1.5
IP_RATE_MINIMUM = 0.1
IP_RATE_MAXIMUM = 3.0
IP_RATE_STEP = 0.02
BLOCKED_IP_FIRST_REST_SECONDS = 45
BLOCKED_IP_LONGEST_REST_SECONDS = 10 * 60
# Refusals other than 429 (a server error or an answer that is not data) in a row that rest an IP.
REFUSALS_BEFORE_REST = 6

SEARCH_PROPERTIES = {'web': '', 'images': 'images', 'news': 'news', 'youtube': 'youtube', 'shopping': 'froogle'}
SEARCH_TYPE_OF_PROPERTY = {code: name for name, code in SEARCH_PROPERTIES.items()}
TIME_RANGE_PRESETS = {
    'past_hour': 'now 1-H',
    'past_4_hours': 'now 4-H',
    'past_day': 'now 1-d',
    'past_7_days': 'now 7-d',
    'past_30_days': 'today 1-m',
    'past_90_days': 'today 3-m',
    'past_12_months': 'today 12-m',
    'past_5_years': 'today 5-y',
    'since_2004': 'all',
}
DEFAULT_TIME_RANGE = 'past_12_months'
REGION_RESOLUTIONS = ('auto', 'country', 'region', 'city', 'dma')
# Google used to list trends of the last 1 to 191 hours and now lists at most 168. A longer period is still accepted,
# so calls that worked before keep working, and is read as the 168 hours there are.
MIN_TRENDING_HOURS = 1
MAX_TRENDING_HOURS = 191
MAX_LISTED_TRENDING_HOURS = TRENDING_PAGE_PERIODS_HOURS[-1]
DEFAULT_TRENDING_HOURS = 24
MAX_TERMS = 2000
MAX_TERM_LENGTH = 100
