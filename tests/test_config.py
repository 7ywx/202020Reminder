from __future__ import annotations

from twenty_twenty_twenty_reminder.config import DailyStats, Settings, load_settings, save_settings
from twenty_twenty_twenty_reminder.timer_state import ReminderClock


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


def test_settings_save_uses_readable_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    save_settings(Settings(work_minutes=25, break_seconds=30, snooze_minutes=3))

    loaded = load_settings()

    assert loaded.work_minutes == 25
    assert loaded.break_seconds == 30
    assert loaded.snooze_minutes == 3


def test_reminder_clock_uses_deadline_time() -> None:
    clock = ReminderClock(20)
    clock.start(now=100.0)

    assert clock.update(now=105.0) == 15
    assert clock.update(now=130.0) == 0
    assert clock.elapsed_seconds == 20


def test_reminder_clock_pause_and_resume_keeps_remaining_time() -> None:
    clock = ReminderClock(20)
    clock.start(now=100.0)

    assert clock.pause(now=108.0) == 12
    assert clock.update(now=500.0) == 12

    clock.start(now=600.0)

    assert clock.update(now=605.0) == 7
