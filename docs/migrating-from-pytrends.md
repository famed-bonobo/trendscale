---
title: Migrating from pytrends to trendscale
description: What still works in pytrends, what Google broke, and how to move a pytrends script to trendscale by changing one import.
---

# Migrating from pytrends to trendscale

[pytrends](https://github.com/GeneralMills/pytrends) is archived on GitHub and its last release, 4.9.2, is from
April 2023. This page says what still works in it, what does not, and how to move a pytrends script to
[trendscale](https://github.com/famed-bonobo/trendscale) by changing one import.

## What still works in pytrends

Checked on 2026-11-03 with pytrends 4.9.2, from a home internet connection:

| pytrends call | Result today |
|---|---|
| `interest_over_time()` with up to 5 terms | Works |
| `interest_over_time()` with 6 or more terms | Fails: `ResponseError: ... code 400` |
| `interest_by_region()` | Works |
| `related_queries()` | Works |
| `suggestions()` | Works |
| `trending_searches()` | Fails: `ResponseError: ... code 404` |
| `today_searches()` | Fails: `ResponseError: ... code 404` |
| `realtime_trending_searches()` | Fails: `ResponseError: ... code 404` |
| 30 single-term `interest_over_time()` calls in a row | All 30 worked, in 37 seconds |

So if you compare five terms or fewer, a few times a day, from your own computer, pytrends may still be enough and
you do not need to switch. The trending calls fail because Google retired the pages they read, and pytrends will
not be updated to follow.

The `429 Too Many Requests` errors that many people report depend on the IP address and on how fast you ask. In our
tests Google Trends refused most requests from cloud data-center IPs, while the same calls from a home connection
went through. pytrends retries with the same session and gives up with `TooManyRequestsError`.

## The one-line change

```bash
pip install "trendscale[pandas]"
```

```python
# from pytrends.request import TrendReq
from trendscale.pytrends import TrendReq

pytrends = TrendReq(hl="en-US", tz=360)
pytrends.build_payload(["python", "javascript", "rust", "go", "java", "kotlin", "swift"], timeframe="today 5-y", geo="US")
pytrends.interest_over_time()            # 7 terms on one scale, one column each plus isPartial, indexed by date
pytrends.interest_by_region(resolution="REGION", inc_geo_code=True)
pytrends.related_queries()               # {term: {"top": DataFrame, "rising": DataFrame}}
pytrends.trending_searches(pn="united_states")
pytrends.suggestions("python")
```

The methods take the same arguments and return the same pandas tables. On 2026-11-03 the seven-term comparison above
took 4.2 seconds, and `trending_searches()` returned 660 searches trending in the United States.

## What changes

| pytrends | trendscale.pytrends | Note |
|---|---|---|
| `build_payload(kw_list, cat, timeframe, geo, gprop)` | Same | `gprop` accepts `""`, `images`, `news`, `youtube`, `froogle` |
| `interest_over_time()` | Same, any number of terms | Past five, the comparisons are chained through an anchor term onto one scale |
| `interest_by_region(resolution, inc_low_vol, inc_geo_code)` | Same, up to five terms | Google compares regions only within one comparison |
| `related_queries()` | Same | |
| `suggestions(keyword)` | Same | |
| `trending_searches(pn)` | Same, working again | `pn` takes pytrends' country names (`united_kingdom`) or a code (`GB`) |
| `today_searches()`, `realtime_trending_searches()` | Use `trending_searches()` | One call now covers what Google shows as trending |
| `related_topics()` | Not available | Google returns an empty list of related topics to automated sessions |
| `categories()`, `top_charts()`, `get_historical_interest()`, `multirange_interest_over_time()` | Not available | |
| `TrendReq(tz=...)` | Accepted and ignored | Times are in UTC |
| `TrendReq(timeout, retries, backoff_factor, requests_args)` | Accepted and ignored | trendscale paces and retries on its own |
| `TrendReq(proxies=[...])` | The first proxy is used | Pass a rotating proxy for large jobs |

## Errors

pytrends raises `ResponseError`, or `TooManyRequestsError` for a 429. In trendscale every error derives from
`TrendsError`:

```python
from trendscale import TrendsError, TrendsBlockedError

try:
    frame = pytrends.interest_over_time()
except TrendsBlockedError:
    ...   # Google kept refusing for three minutes: wait, ask less often, or use a proxy
except TrendsError:
    ...   # any other trendscale error
```

trendscale starts at about 1.5 requests per second, speeds up while answers come clean, halves the pace when Google
pushes back, and rests the IP: 45 seconds at first, longer if the block persists. It raises `TrendsBlockedError` only
after three minutes of waiting, so a script that used to stop at the first 429 keeps going.

## Going further than pytrends

The pytrends module is a thin layer over trendscale's own API, which returns plain dictionaries and needs no pandas:

```python
from trendscale import Trends

with Trends() as trends:
    timelines = trends.interest_over_time(["chatgpt", "gemini", "claude", "perplexity", "copilot", "deepseek", "grok"], geo="US")
    records = trends.explore(["python", "javascript"], geo="US", time_range="past_5_years")   # timeline, regions, related queries
    trending = trends.trending_now("US", hours=24, limit=10)   # with search volume, growth and start time
```

It also has an async client, a command line (`trendscale compare python javascript rust --geo US`) and type hints.
See the [README](https://github.com/famed-bonobo/trendscale#readme).

## Running it at scale

For thousands of terms on a schedule, without managing proxies, the same data is available as a hosted
[Google Trends Scraper on Apify](https://apify.com/famed_bonobo/google-trends-scraper) by the same author, at $1 per
1,000 terms with their timeline, regions and related queries.
