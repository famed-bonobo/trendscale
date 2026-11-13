# Changelog

## 0.1.1 (2026-11-12)

- Fixed `trending_now()`, the `trendscale trending` command and `TrendReq.trending_searches()`, which failed on every
  call since Google retired the internal call they used (November 2026). The list is now read from the data that
  Google's Trending now page embeds. The records keep the same fields.
- Google now lists the trends of the last 4, 24, 48 or 168 hours only. Any other `hours` is answered from the shortest
  of those periods that covers it, keeping the trends that started within the hours asked for.
- The longest period Google lists went from 191 to 168 hours. `hours` from 169 to 191 is still accepted and read as
  168: the records carry `hours: 168` and a `trendsUrl` for seven days.

## 0.1.0 (2026-11-03)

First release.

- `explore()` and `interest_over_time()` for any number of terms on one 0-100 scale, chained through an anchor term,
  with interest by region and related queries.
- `trending_now()` and `suggestions()`.
- `AsyncTrends` with the same methods, the `trendscale` command line, and `trendscale.pytrends.TrendReq`, a drop-in
  replacement for pytrends.
