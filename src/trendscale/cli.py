"""The trendscale command: compare terms over time, list what is trending now, or find topic ids; JSON or CSV.

trendscale compare python javascript rust go java kotlin --geo US --time-range past_5_years --format csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from ._protocol import constants
from .client import Trends
from .errors import TrendsError


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    # Terms and trends come in every language; a Windows console would otherwise write them in its code page.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        with Trends(language=arguments.language, proxy=arguments.proxy) as trends:
            rows = _run(trends, arguments)
    except TrendsError as error:
        print(f'trendscale: {error}', file=sys.stderr)
        return 1
    _write(rows, arguments.format)
    return 0


def _run(trends: Trends, arguments: argparse.Namespace) -> list[dict[str, Any]]:
    if arguments.command == 'compare':
        timelines = trends.interest_over_time(
            arguments.terms,
            geo=arguments.geo,
            time_range=arguments.time_range,
            search_type=arguments.search_type,
            anchor=arguments.anchor,
        )
        return _table(timelines)
    if arguments.command == 'trending':
        return trends.trending_now(arguments.geo, hours=arguments.hours, limit=arguments.limit)
    return trends.suggestions(arguments.text)


def _table(timelines: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """One row per date with one column per term, the shape spreadsheets and charts expect."""
    terms = list(timelines)
    first = timelines[terms[0]] if terms else []
    return [
        {'date': point['date'], **{term: timelines[term][index]['value'] for term in terms}, 'isPartial': point['isPartial']}
        for index, point in enumerate(first)
    ]


def _write(rows: list[dict[str, Any]], output_format: str) -> None:
    if output_format == 'json':
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write('\n')
        return
    # CSV keeps one row per record; nested values (categories, related searches) are written as JSON text.
    columns = list(dict.fromkeys(column for row in rows for column in row))
    writer = csv.DictWriter(sys.stdout, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='trendscale', description='Google Trends: any number of terms on one scale, trending now, topics.'
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    commands = parser.add_subparsers(dest='command', required=True)
    compare = commands.add_parser('compare', help='interest over time of any number of terms on one 0-100 scale')
    compare.add_argument('terms', nargs='+')
    compare.add_argument('--geo', default='', help='a code such as US or US-CA; empty for the whole world')
    compare.add_argument(
        '--time-range',
        default=constants.DEFAULT_TIME_RANGE,
        help=f'{", ".join(constants.TIME_RANGE_PRESETS)}, a Google code such as "today 5-y", or "2024-01-01 2024-06-30"',
    )
    compare.add_argument('--search-type', choices=list(constants.SEARCH_PROPERTIES), default='web')
    compare.add_argument('--anchor', help='the term that links comparisons past five; the first term by default')
    trending = commands.add_parser('trending', help='what people search right now in a country')
    trending.add_argument('geo', nargs='?', default='US')
    trending.add_argument('--hours', type=int, default=constants.DEFAULT_TRENDING_HOURS)
    trending.add_argument('--limit', type=int)
    suggest = commands.add_parser('suggest', help='Google topics and their ids for a text')
    suggest.add_argument('text')
    for command in (compare, trending, suggest):
        command.add_argument('--language', default=constants.DEFAULT_LANGUAGE, help="Google's hl code, such as en-US or es")
        command.add_argument('--proxy', help='http(s) or socks proxy URL')
        command.add_argument('--format', choices=['json', 'csv'], default='csv' if command is compare else 'json')
    return parser


if __name__ == '__main__':
    raise SystemExit(main())
