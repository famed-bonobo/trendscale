"""Builds the form of the batchexecute call that returns the "Trending now" list."""

from __future__ import annotations

import json

from . import constants as config

COMPACT_SEPARATORS = (',', ':')
NO_NEWS = 0


def trending_form(geo: str, hours: int, language: str) -> dict[str, str]:
    """The form body of the trending-now RPC: region, language (two letters) and hours.

    The fourth argument asked for news articles. Since late October 2026 Google answers any value but 0 with status 3
    and serves the news only through a separate call that needs a reCAPTCHA token, so none are asked for.
    """
    arguments = [None, None, geo, NO_NEWS, language[:2], hours, config.TRENDING_WITH_NEWS_FLAG]
    envelope = [
        [[config.TRENDING_NOW_RPC, json.dumps(arguments, separators=COMPACT_SEPARATORS, ensure_ascii=False), None, 'generic']]
    ]
    return {'f.req': json.dumps(envelope, separators=COMPACT_SEPARATORS, ensure_ascii=False)}


def trending_parameters(language: str) -> dict[str, str]:
    return {'hl': language}
