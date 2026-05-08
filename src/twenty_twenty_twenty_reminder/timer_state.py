from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True)
class ReminderClock:
    """Deadline-based countdown state that is resilient to timer drift."""

    duration_seconds: int
    remaining_seconds: int
    deadline: float | None = None
    started_at: float | None = None

    def __init__(self, duration_seconds: int) -> None:
        self.duration_seconds = max(1, int(duration_seconds))
        self.remaining_seconds = self.duration_seconds
        self.deadline = None
        self.started_at = None

    @property
    def elapsed_seconds(self) -> int:
        return max(0, self.duration_seconds - self.remaining_seconds)

    @property
    def is_running(self) -> bool:
        return self.deadline is not None

    def reset(self, duration_seconds: int | None = None, *, start: bool = False, now: float | None = None) -> None:
        if duration_seconds is not None:
            self.duration_seconds = max(1, int(duration_seconds))
        self.remaining_seconds = self.duration_seconds
        self.deadline = None
        self.started_at = None
        if start:
            self.start(now=now)

    def start(self, duration_seconds: int | None = None, *, now: float | None = None) -> None:
        if duration_seconds is not None:
            self.duration_seconds = max(1, int(duration_seconds))
            self.remaining_seconds = self.duration_seconds
        current = monotonic() if now is None else now
        self.started_at = current
        self.deadline = current + self.remaining_seconds

    def pause(self, *, now: float | None = None) -> int:
        if self.deadline is None:
            return self.remaining_seconds
        self.update(now=now)
        self.deadline = None
        self.started_at = None
        return self.remaining_seconds

    def update(self, *, now: float | None = None) -> int:
        if self.deadline is None:
            return self.remaining_seconds
        current = monotonic() if now is None else now
        self.remaining_seconds = max(0, int(round(self.deadline - current)))
        return self.remaining_seconds
