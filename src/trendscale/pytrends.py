"""A drop-in replacement for pytrends' TrendReq, built on trendscale. Change one import and keep your code:

    # from pytrends.request import TrendReq
    from trendscale.pytrends import TrendReq

    pytrends = TrendReq(hl="en-US")
    pytrends.build_payload(["python", "javascript", "rust", "go", "java", "kotlin"], timeframe="today 5-y", geo="US")
    frame = pytrends.interest_over_time()

The same methods return the same pandas tables. Differences: interest_over_time() takes any number of terms (pytrends
stops at five), all on one scale; times are in UTC, so `tz` is accepted and ignored; related_topics(), categories()
and the old daily and realtime trending calls are not available, because Google retired or changed what they read.
Needs pandas: pip install "trendscale[pandas]".
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from ._protocol import constants
from .client import Trends
from .errors import InvalidOptionError
from .options import RegionResolution

if TYPE_CHECKING:
    import pandas

# pytrends' region levels and the names its trending_searches() took for countries.
RESOLUTIONS = {'COUNTRY': 'country', 'REGION': 'region', 'CITY': 'city', 'DMA': 'dma'}
COUNTRY_CODES = {
    'argentina': 'AR',
    'australia': 'AU',
    'austria': 'AT',
    'belgium': 'BE',
    'brazil': 'BR',
    'canada': 'CA',
    'chile': 'CL',
    'colombia': 'CO',
    'czech_republic': 'CZ',
    'denmark': 'DK',
    'egypt': 'EG',
    'finland': 'FI',
    'france': 'FR',
    'germany': 'DE',
    'greece': 'GR',
    'hong_kong': 'HK',
    'hungary': 'HU',
    'india': 'IN',
    'indonesia': 'ID',
    'ireland': 'IE',
    'israel': 'IL',
    'italy': 'IT',
    'japan': 'JP',
    'kenya': 'KE',
    'malaysia': 'MY',
    'mexico': 'MX',
    'netherlands': 'NL',
    'new_zealand': 'NZ',
    'nigeria': 'NG',
    'norway': 'NO',
    'philippines': 'PH',
    'poland': 'PL',
    'portugal': 'PT',
    'romania': 'RO',
    'russia': 'RU',
    'saudi_arabia': 'SA',
    'singapore': 'SG',
    'south_africa': 'ZA',
    'south_korea': 'KR',
    'spain': 'ES',
    'sweden': 'SE',
    'switzerland': 'CH',
    'taiwan': 'TW',
    'thailand': 'TH',
    'turkey': 'TR',
    'ukraine': 'UA',
    'united_kingdom': 'GB',
    'united_states': 'US',
    'vietnam': 'VN',
}
GPROPS = {'': 'web', 'images': 'images', 'news': 'news', 'youtube': 'youtube', 'froogle': 'shopping'}
INTEREST_BY_REGION_TERM_LIMIT = constants.MAX_TERMS_PER_COMPARISON


class TrendReq:
    """pytrends' TrendReq: set the search with build_payload(), then read each chart."""

    def __init__(
        self,
        hl: str = constants.DEFAULT_LANGUAGE,
        tz: int = 0,
        geo: str = '',
        timeout: Any = None,
        proxies: Sequence[str] | str = '',
        retries: int = 0,
        backoff_factor: float = 0,
        requests_args: Any = None,
    ) -> None:
        # timeout, retries, backoff_factor and requests_args belong to pytrends' requests session; trendscale paces and
        # retries on its own, so they are accepted for compatibility and not used.
        proxy = proxies if isinstance(proxies, str) else next(iter(proxies), '')
        self._trends = Trends(language=hl, proxy=proxy or None)
        self.geo = geo
        self.kw_list: list[str] = []
        self._search: dict[str, Any] = {}

    def build_payload(
        self, kw_list: Sequence[str], cat: int = 0, timeframe: str = 'today 5-y', geo: str = '', gprop: str = ''
    ) -> None:
        if gprop not in GPROPS:
            raise InvalidOptionError(f'gprop must be one of {list(GPROPS)}, got {gprop!r}')
        self.kw_list = list(kw_list)
        self._search = {'geo': geo or self.geo, 'time_range': timeframe, 'category': cat, 'search_type': GPROPS[gprop]}

    def interest_over_time(self) -> pandas.DataFrame:
        """One column per term on one shared scale, an isPartial column, and the dates as the index."""
        pd = _pandas()
        records = self._trends.explore(self._terms(), regions=False, related_queries=False, **self._search)
        if not records or not records[0]['timeline']:
            return cast('pandas.DataFrame', pd.DataFrame())
        dates = pd.to_datetime([point['timestamp'] for point in records[0]['timeline']], unit='s')
        frame = pd.DataFrame(
            {record['term']: [point['value'] for point in record['timeline']] for record in records}, index=dates
        )
        frame['isPartial'] = [point['isPartial'] for point in records[0]['timeline']]
        frame.index.name = 'date'
        return cast('pandas.DataFrame', frame)

    def interest_by_region(
        self, resolution: str = 'COUNTRY', inc_low_vol: bool = False, inc_geo_code: bool = False
    ) -> pandas.DataFrame:
        """One row per region, one column per term; Google compares regions for at most five terms at once."""
        pd = _pandas()
        terms = self._terms()
        if len(terms) > INTEREST_BY_REGION_TERM_LIMIT:
            raise InvalidOptionError(
                f'Google compares regions for at most {INTEREST_BY_REGION_TERM_LIMIT} terms; got {len(terms)}'
            )
        if resolution not in RESOLUTIONS:
            raise InvalidOptionError(f'resolution must be one of {list(RESOLUTIONS)}, got {resolution!r}')
        records = self._trends.explore(
            terms,
            regions=True,
            related_queries=False,
            region_resolution=cast('RegionResolution', RESOLUTIONS[resolution]),
            low_volume_regions=inc_low_vol,
            **self._search,
        )
        rows: dict[str, dict[str, Any]] = {}
        for record in records:
            for region in record['regions'] or []:
                row = rows.setdefault(region['geoName'], {'geoCode': region['geoCode']})
                row[record['term']] = region['value']
        frame = pd.DataFrame.from_dict(rows, orient='index').fillna(0)
        frame.index.name = 'geoName'
        columns = [record['term'] for record in records if record['term'] in frame.columns]
        return cast('pandas.DataFrame', frame[(['geoCode'] if inc_geo_code else []) + columns])

    def related_queries(self) -> dict[str, dict[str, pandas.DataFrame | None]]:
        """{term: {"top": DataFrame(query, value), "rising": DataFrame(query, value)}}, None where Google shows none."""
        pd = _pandas()
        records = self._trends.explore(self._terms(), regions=False, related_queries=True, **self._search)
        result: dict[str, dict[str, pandas.DataFrame | None]] = {}
        for record in records:
            related = record['relatedQueries'] or {}
            result[record['term']] = {
                kind: pd.DataFrame([{'query': item['query'], 'value': item['value']} for item in related[kind]])
                if related.get(kind)
                else None
                for kind in ('top', 'rising')
            }
        return result

    def suggestions(self, keyword: str) -> list[dict[str, str | None]]:
        return [
            {'mid': item['topicId'], 'title': item['title'], 'type': item['kind']} for item in self._trends.suggestions(keyword)
        ]

    def trending_searches(self, pn: str = 'united_states') -> pandas.DataFrame:
        """Today's trending searches of a country, by pytrends' country name ("united_kingdom") or a code ("GB")."""
        pd = _pandas()
        code = COUNTRY_CODES.get(pn.lower(), pn.upper())
        return cast('pandas.DataFrame', pd.DataFrame([row['query'] for row in self._trends.trending_now(code)]))

    def related_topics(self) -> dict[str, Any]:
        raise NotImplementedError('related_topics() is not available in trendscale; related_queries() is.')

    def _terms(self) -> list[str]:
        if not self.kw_list:
            raise InvalidOptionError('Call build_payload() with your terms first')
        return self.kw_list


def _pandas() -> Any:
    try:
        import pandas
    except ImportError as error:
        raise ImportError('trendscale.pytrends returns pandas tables: pip install "trendscale[pandas]"') from error
    return pandas
