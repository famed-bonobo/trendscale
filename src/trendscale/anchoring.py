"""Puts more than five search terms on one 0-100 scale by chaining Google's five-term comparisons through an anchor term.

Google scales each comparison so its highest point is 100, so two comparisons cannot be read against each other. Every
batch here holds the anchor plus up to four other terms; the anchor's total interest in a batch against its total in
the first batch is the factor that brings that batch onto the first one's scale, and the whole result is then scaled
so its highest point is 100.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._protocol import constants as config
from .errors import AnchorUnreadableError

OTHER_TERMS_PER_BATCH = config.MAX_TERMS_PER_COMPARISON - 1
SCALE_MAXIMUM = 100.0
VALUE_DECIMALS = 1
# Google's values are whole numbers; an anchor this faint in a batch leaves the factor too coarse to trust.
MIN_RELIABLE_ANCHOR_TOTAL = 20


@dataclass(frozen=True)
class RescaledTerm:
    values: list[float]
    scale_factor: float


@dataclass(frozen=True)
class AnchoredResult:
    terms: dict[str, RescaledTerm]
    # Batches whose anchor total was below MIN_RELIABLE_ANCHOR_TOTAL: their terms are placed less precisely.
    imprecise_batches: list[int]


def split_batches(terms: list[str], anchor: str) -> list[list[str]]:
    """Batches of the anchor plus up to four other terms each; the anchor leads every batch."""
    others = [term for term in terms if term != anchor]
    return [
        [anchor, *others[start : start + OTHER_TERMS_PER_BATCH]] for start in range(0, max(len(others), 1), OTHER_TERMS_PER_BATCH)
    ]


def rescale(batches: list[dict[str, list[int]]], anchor: str) -> AnchoredResult:
    """Each batch maps a term to its values (same dates in every batch); returns every term on one scale, the anchor once."""
    reference_total = sum(batches[0][anchor])
    if not reference_total:
        raise AnchorUnreadableError(
            f'The anchor term {anchor!r} has no search interest in the period, so other terms cannot be compared to it'
        )
    imprecise: list[int] = []
    factors: list[float] = []
    for index, batch in enumerate(batches):
        anchor_total = sum(batch[anchor])
        if not anchor_total:
            raise AnchorUnreadableError(
                f'The anchor term {anchor!r} has no search interest next to {_others(batch, anchor)}; pick a more popular anchor'
            )
        if anchor_total < MIN_RELIABLE_ANCHOR_TOTAL:
            imprecise.append(index)
        factors.append(reference_total / anchor_total)
    shared: dict[str, tuple[list[float], float]] = {}
    for batch, factor in zip(batches, factors, strict=True):
        for term, values in batch.items():
            if term not in shared:
                shared[term] = ([value * factor for value in values], factor)
    top = max((max(values, default=0) for values, _ in shared.values()), default=0)
    unit = SCALE_MAXIMUM / top if top else 1.0
    return AnchoredResult(
        terms={
            term: RescaledTerm([round(value * unit, VALUE_DECIMALS) for value in values], factor * unit)
            for term, (values, factor) in shared.items()
        },
        imprecise_batches=imprecise,
    )


def _others(batch: dict[str, list[int]], anchor: str) -> list[str]:
    return [term for term in batch if term != anchor]
