from __future__ import annotations

from twenty_twenty_twenty_reminder.config import DailyStats, Settings


def test_settings_clamps_invalid_values() -> None:
    settings = Settings.from_dict(
        {
            "work_minutes": -10,
            "break_seconds": "bad",
            "snooze_minutes": 99,
            "distance_text": "",
        }
    )
    assert settings.work_minutes == 1
    assert settings.break_seconds == 20
    assert settings.snooze_minutes == 30
    assert settings.distance_text == "20英尺/约6米以外"


def test_settings_keeps_at_least_one_visual_reminder() -> None:
    settings = Settings.from_dict(
        {
            "enable_notifications": False,
            "enable_popup": False,
            "enable_fullscreen": False,
        }
    )
    assert settings.enable_popup is True


def test_daily_stats_completion_rate() -> None:
    stats = DailyStats(completed_breaks=8, skipped_breaks=2)
    assert stats.completion_rate == 0.8


def test_daily_stats_handles_empty_rate() -> None:
    stats = DailyStats()
    assert stats.completion_rate == 0.0


def test_default_starts_waiting_for_user() -> None:
    settings = Settings()
    assert settings.start_paused is True
