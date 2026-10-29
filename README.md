# trendscale

[![PyPI](https://img.shields.io/pypi/v/trendscale)](https://pypi.org/project/trendscale/)
[![Python](https://img.shields.io/pypi/pyversions/trendscale)](https://pypi.org/project/trendscale/)
[![Tests](https://github.com/famed-bonobo/trendscale/actions/workflows/tests.yml/badge.svg)](https://github.com/famed-bonobo/trendscale/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**A Google Trends API for Python that compares any number of terms on one 0-100 scale.** Google compares at most five
terms at a time and rescales every comparison, so separate comparisons cannot be read against each other.
trendscale chains them through an anchor term and puts all your terms on one scale. It also reads interest by
region, related queries, what is trending now, and topic ids. A maintained replacement for pytrends (archived
since 2024), with a drop-in `TrendReq`.

```python
from trendscale import Trends

with Trends() as trends:
    timelines = trends.interest_over_time(
        ["chatgpt", "gemini", "claude", "perplexity", "copilot", "deepseek", "grok"], geo="US", time_range="past_12_months",
    )
```

Seven terms, one chart, 2.9 seconds. The average of the last four weeks in the United States (October 2026):

| chatgpt | gemini | claude | copilot | grok | deepseek | perplexity |
|---:|---:|---:|---:|---:|---:|---:|
| 79.0 | 34.8 | 24.5 | 5.2 | 4.8 | 1.8 | 1.0 |

- **Any number of terms on one scale**, 7 or 700. Checked against Google's own five-term comparison, the chained
  values differ by 0.03 points on average.
- **Moving from pytrends takes one line:** `from trendscale.pytrends import TrendReq`. Same methods, same pandas tables,
  no five-term limit.
- **Paced for Google:** it sends requests at the pace Google tolerates from one IP and rests the IP when Google
  pushes back, instead of failing with a wall of 429 errors. The first 429 of a session, which only hands out
  Google's cookie, is recognised and retried at once.
- **Interest by region** (country, region, city, DMA) and **related queries** with Breakout growth.
- **Trending now** for any country: search volume, growth, when it started, categories and related searches.
- **Topic ids** from Google's suggestions, to search "Python (programming language)" instead of the word.
- Sync and **async** clients, a **command line**, type hints, and 76 tests (5 of them against Google itself).

## Install

```bash
pip install trendscale            # pip install "trendscale[pandas]" for the pytrends-compatible module
```

Python 3.11 or newer. The only dependency is [httpx](https://www.python-httpx.org/).

## Usage

### Interest over time, by region, and related queries

```python
from trendscale import Trends

trends = Trends(language="en-US")

records = trends.explore(["python", "javascript"], geo="US", time_range="past_5_years")
python = records[0]
python["timeline"][0]      # {'date': '2021-10-24', 'timestamp': 1635033600, 'value': 60, 'hasData': True, 'isPartial': False}
python["summary"]          # {'average': 67.5, 'peakValue': 100, 'peakDate': '2026-06-14', 'latestValue': 38}
python["regions"][0]       # {'geoCode': 'US-NM', 'geoName': 'New Mexico', 'value': 88, 'latitude': None, 'longitude': None}
python["relatedQueries"]   # {'top': [{'query': 'python list', 'value': 100, ...}, ...], 'rising': [...]}
python["trendsUrl"]        # the same chart on trends.google.com
```

`explore()` returns one record per term. `interest_over_time()` skips the region and related-query calls and returns
`{term: timeline}`, so it is the fastest call.

| Argument | Values |
|---|---|
| `geo` | `""` for the whole world, or a code such as `US`, `US-CA`, `GB-ENG` |
| `time_range` | `past_hour`, `past_4_hours`, `past_day`, `past_7_days`, `past_30_days`, `past_90_days`, `past_12_months` (default), `past_5_years`, `since_2004`; a Google code such as `today 5-y` or `now 7-d`; two dates `"2024-01-01 2024-06-30"` or a pair of `date` objects; or hours `"2026-10-20T08 2026-10-21T20"` (up to 7 days) |
| `search_type` | `web`, `images`, `news`, `youtube`, `shopping` |
| `category` | a Google Trends category id; `0` for all |
| `anchor` | the term that links the comparisons past five; the first term by default |
| `separate` | `True` to scale each term on its own, as Google shows a single term |
| `regions`, `region_resolution`, `low_volume_regions` | interest by region: `auto`, `country`, `region`, `city`, `dma` |
| `related_queries` | `True` by default |

**How the chain works.** Each comparison holds the anchor and four other terms. The anchor's total interest in a
comparison, against its total in the first one, is the factor that brings that comparison onto the first one's
scale. Then the whole result is scaled so its highest point is 100. Every anchored record says so in its `anchor`
field, with `isPrecise: False` when the anchor was too faint in some comparison to place it exactly. Pick an anchor
that is neither the most nor the least searched of your terms.

### Moving from pytrends

```python
# from pytrends.request import TrendReq
from trendscale.pytrends import TrendReq

pytrends = TrendReq(hl="en-US", tz=360)
pytrends.build_payload(["python", "javascript", "rust", "go", "java", "kotlin", "swift"], timeframe="today 5-y", geo="US")
pytrends.interest_over_time()            # DataFrame: one column per term plus isPartial, indexed by date
pytrends.interest_by_region(resolution="REGION", inc_geo_code=True)
pytrends.related_queries()               # {term: {"top": DataFrame, "rising": DataFrame}}
pytrends.trending_searches(pn="united_kingdom")
pytrends.suggestions("python")
```

Differences from pytrends: `interest_over_time()` takes any number of terms; times are in UTC, so `tz` is accepted
and ignored; `interest_by_region()` stays at five terms (Google compares regions only within one comparison);
`related_topics()`, `categories()` and the old daily and realtime trending calls are not available.

### Trending now and topics

```python
trends.trending_now("US", hours=24, limit=10)
# [{'rank': 1, 'query': 'patrick stewart', 'searchVolume': 2000000, 'searchVolumeLabel': '2M+', 'volumeGrowthPercent': 1000,
#   'startedAt': '2026-10-29T19:30:00Z', 'isActive': True, 'relatedQueries': [...], 'categories': [...], ...}]

trends.suggestions("python")
# [{'title': 'Python', 'topicId': '/m/05z1_', 'kind': 'Programming language'}, ...]
trends.explore(["/m/05z1_"])             # the topic, whatever words people use for it
```

Google shows news articles next to each trend on its page, but since October 2026 it serves them only behind a
reCAPTCHA check, so trendscale does not return them.

### Async

```python
import asyncio
from trendscale import AsyncTrends

async def main():
    async with AsyncTrends() as trends:
        countries = ["US", "GB", "IN", "BR"]
        results = await asyncio.gather(*(trends.interest_over_time(["python", "javascript"], geo=geo) for geo in countries))

asyncio.run(main())
```

### Command line

```bash
trendscale compare chatgpt gemini claude perplexity copilot deepseek grok --geo US > assistants.csv
trendscale compare python javascript --time-range "today 5-y" --format json
trendscale trending GB --limit 20
trendscale suggest python
```

## Errors, rate limits and proxies

Every error derives from `TrendsError`. Google limits how much one IP can ask for. trendscale starts at about 1.5
requests per second, speeds up while answers come clean, halves the pace on a block, and rests the IP: 45 seconds at
first, longer if the block persists. A call gives up with `TrendsBlockedError` after three minutes of waiting. For
large or scheduled jobs, pass a rotating proxy:

```python
Trends(proxy="http://user:password@proxy.example.com:8000")   # socks5:// needs: pip install "trendscale[socks]"
```

## Running it at scale

If you need thousands of terms on a schedule without managing proxies or servers, the same data is available as a
hosted [Google Trends Scraper on Apify](https://apify.com/famed_bonobo/google-trends-scraper) by the same author.
Its records use the same field names as `explore()`, so code that reads one reads the other. It costs $1 per 1,000
terms with their timeline, regions and related queries, and runs spread over Apify's IPs, with schedules, webhooks and
exports to CSV, Excel or Google Sheets.

## How it works

trends.google.com loads each chart from internal endpoints: an explore call returns one widget per chart with a
token, and each chart's data is fetched with that token. trendscale sends the same calls the page sends, and the
trending list comes from the page's own `batchexecute` call. No browser is involved. The calls were checked against
live answers in October 2026. When Google changes them, the live tests (`pytest -m live`, run every Monday on GitHub)
show which part broke.

## FAQ

**Is there an official Google Trends API?** Google opened an alpha of an official Trends API in July 2025, for a small
group of approved testers, without Trending now. trendscale reads the same public charts anyone can open at trends.google.com.

**Why do my numbers differ from trends.google.com?** Google scales every chart so its highest point is 100. A term
compared with others, or chained onto one scale, has different numbers than the same term alone. Use `separate=True`
for the single-term numbers.

**Is it allowed?** trendscale reads the same public charts anyone can open in a browser, and returns aggregated
search interest, no personal data. You are responsible for how you use the data and for following the terms that
apply to you. This project is not affiliated with Google.

## Development

```bash
pip install -e ".[pandas]" pytest pytest-asyncio ruff mypy pandas-stubs
pytest              # 71 offline tests, on real Google answers recorded in tests/fixtures
pytest -m live      # 5 tests against Google
ruff check src tests && mypy src
```

Issues and pull requests are welcome.

This library was written with the help of an AI coding agent (Claude, by Anthropic). Every method was run against
Google and the results checked before release.

## License

[MIT](LICENSE)
