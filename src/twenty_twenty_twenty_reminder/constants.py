from __future__ import annotations

from importlib.resources import files

APP_DISPLAY_NAME = "202020Reminder"
APP_SUBTITLE = "20-20-20 Eye Break Reminder"
APP_VERSION = "0.4.2"
DEFAULT_DISTANCE_TEXT = "20英尺/约6米以外"


def asset_path(relative_path: str) -> str:
    return str(files("twenty_twenty_twenty_reminder").joinpath(relative_path))


def format_mmss(total_seconds: int) -> str:
    minutes, seconds = divmod(max(0, total_seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"
