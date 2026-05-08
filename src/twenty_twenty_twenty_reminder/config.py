from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

APP_NAME = "202020Reminder"
APP_PACKAGE = "twenty_twenty_twenty_reminder"
CONFIG_VERSION = 3


def app_data_dir() -> Path:
    """Return a writable app data directory.

    On Windows this uses %APPDATA%/202020Reminder. On other systems it falls
    back to ~/.config/202020Reminder so contributors can still test locally.
    """
    appdata = os.getenv("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return app_data_dir() / "settings.json"


def stats_file() -> Path:
    return app_data_dir() / "stats.json"


@dataclass(slots=True)
class Settings:
    """User configurable reminder settings."""

    config_version: int = CONFIG_VERSION
    work_minutes: int = 20
    break_seconds: int = 20
    distance_text: str = "20英尺/约6米以外"
    enable_sound: bool = True
    enable_notifications: bool = True
    enable_popup: bool = True
    enable_fullscreen: bool = False
    always_on_top: bool = True
    start_paused: bool = True
    snooze_minutes: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        defaults = asdict(cls())
        cleaned: dict[str, Any] = {}
        for key, default_value in defaults.items():
            cleaned[key] = data.get(key, default_value)

        cleaned["config_version"] = CONFIG_VERSION
        cleaned["work_minutes"] = _clamp_int(cleaned["work_minutes"], 1, 180, 20)
        cleaned["break_seconds"] = _clamp_int(cleaned["break_seconds"], 5, 600, 20)
        cleaned["distance_text"] = str(cleaned["distance_text"] or defaults["distance_text"]).strip()
        cleaned["enable_sound"] = bool(cleaned["enable_sound"])
        cleaned["enable_notifications"] = bool(cleaned["enable_notifications"])
        cleaned["enable_popup"] = bool(cleaned["enable_popup"])
        cleaned["enable_fullscreen"] = bool(cleaned["enable_fullscreen"])
        cleaned["always_on_top"] = bool(cleaned["always_on_top"])
        cleaned["start_paused"] = bool(cleaned["start_paused"])
        cleaned["snooze_minutes"] = _clamp_int(cleaned["snooze_minutes"], 1, 30, 1)

        # Avoid a silent reminder when the user accidentally disables all visual modes.
        if not (cleaned["enable_notifications"] or cleaned["enable_popup"] or cleaned["enable_fullscreen"]):
            cleaned["enable_popup"] = True

        return cls(**cleaned)


@dataclass(slots=True)
class DailyStats:
    """A small privacy-friendly local stats model.

    The app only stores aggregate counts on the user's own machine. No login,
    telemetry, network calls, or analytics are used.
    """

    day: str = date.today().isoformat()
    completed_breaks: int = 0
    skipped_breaks: int = 0
    snoozed_breaks: int = 0
    total_rest_seconds: int = 0
    longest_focus_minutes: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyStats":
        today = date.today().isoformat()
        if data.get("day") != today:
            return cls(day=today)
        return cls(
            day=today,
            completed_breaks=_clamp_int(data.get("completed_breaks"), 0, 10000, 0),
            skipped_breaks=_clamp_int(data.get("skipped_breaks"), 0, 10000, 0),
            snoozed_breaks=_clamp_int(data.get("snoozed_breaks"), 0, 10000, 0),
            total_rest_seconds=_clamp_int(data.get("total_rest_seconds"), 0, 24 * 3600, 0),
            longest_focus_minutes=_clamp_int(data.get("longest_focus_minutes"), 0, 24 * 60, 0),
        )

    @property
    def completion_rate(self) -> float:
        total = self.completed_breaks + self.skipped_breaks
        if total == 0:
            return 0.0
        return self.completed_breaks / total


def _clamp_int(value: Any, low: int, high: int, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return min(max(number, low), high)


def load_settings() -> Settings:
    path = config_file()
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return Settings()
        return Settings.from_dict(data)
    except (OSError, json.JSONDecodeError):
        return Settings()


def save_settings(settings: Settings) -> None:
    _write_json_atomic(config_file(), asdict(settings))


def load_stats() -> DailyStats:
    path = stats_file()
    if not path.exists():
        return DailyStats()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return DailyStats()
        return DailyStats.from_dict(data)
    except (OSError, json.JSONDecodeError):
        return DailyStats()


def save_stats(stats: DailyStats) -> None:
    _write_json_atomic(stats_file(), asdict(stats))


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp_file:
        temp_file.write(payload)
        temp_file.write("\n")
        temp_path = Path(temp_file.name)
    temp_path.replace(path)
