"""Paces the requests from one IP at the rate Google tolerates, and rests the IP while Google blocks it.

The pace grows a little with each clean answer, as TCP does; a block halves it. A blocked IP rests, and when the
rest ends one request tests it: data brings it back, another block doubles the rest. Google's random refusals
(error 13) also depend on the IP (one IP got 16 in a row and no data, 2026-10-16), so a run of them rests it too. A block can lift
within minutes or last about 18 (measured 2026-10-16), so short first rests recover an IP that was briefly turned away.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PaceLimits:
    initial_rate: float
    minimum_rate: float
    maximum_rate: float
    rate_step: float
    first_rest_seconds: float
    longest_rest_seconds: float
    refusals_before_rest: int

    def __post_init__(self) -> None:
        if not 0 < self.minimum_rate <= self.initial_rate <= self.maximum_rate:
            raise ValueError(f'Rates must satisfy 0 < minimum <= initial <= maximum, got {self}')
        if not 0 < self.first_rest_seconds <= self.longest_rest_seconds:
            raise ValueError(f'Rests must satisfy 0 < first <= longest, got {self}')


class IpPace:
    def __init__(self, limits: PaceLimits) -> None:
        self._limits = limits
        self._rate = limits.initial_rate
        self._next_start = 0.0
        self._resting_until = 0.0
        self._last_rest_at = 0.0
        self._rest_seconds = limits.first_rest_seconds
        self._refusals_in_a_row = 0

    def rest_remaining(self) -> float:
        return max(0.0, self._resting_until - time.monotonic())

    def wait_seconds(self) -> float:
        return max(0.0, self._next_start - time.monotonic())

    def take_turn(self) -> float:
        """Mark a request as sent now and return its start time."""
        now = time.monotonic()
        self._next_start = now + 1 / self._rate
        return now

    def record(self, started_at: float, was_blocked: bool) -> float | None:
        """Learn from one response; return the length of the rest it starts, if it starts one."""
        limits = self._limits
        if not was_blocked:
            # About one step per second of responses that are not blocks, whatever the current rate.
            self._rate = min(limits.maximum_rate, self._rate + limits.rate_step / self._rate)
            return None
        self._rate = max(limits.minimum_rate, self._rate / 2)
        return self._rest(started_at)

    def note_data(self) -> None:
        """Google sent data: the IP is healthy, so its next rest starts short again."""
        self._refusals_in_a_row = 0
        self._rest_seconds = self._limits.first_rest_seconds

    def note_refusal(self, started_at: float) -> float | None:
        """Google refused at random (error 13); return the length of the rest a run of refusals starts, if any."""
        self._refusals_in_a_row += 1
        if self._refusals_in_a_row < self._limits.refusals_before_rest:
            return None
        self._refusals_in_a_row = 0
        return self._rest(started_at)

    def _rest(self, started_at: float) -> float | None:
        # Requests sent before the IP was rested met the old pace; counting their answers would rest it twice.
        if started_at < self._last_rest_at:
            return None
        limits = self._limits
        now = time.monotonic()
        self._last_rest_at = now
        self._resting_until = now + self._rest_seconds
        # Only one request tests the IP when the rest ends; the next waits a full interval for its answer.
        self._next_start = max(self._next_start, self._resting_until)
        rest = self._rest_seconds
        self._rest_seconds = min(limits.longest_rest_seconds, rest * 2)
        return rest
