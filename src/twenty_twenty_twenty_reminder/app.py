from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QStyle, QSystemTrayIcon

from .config import load_settings, load_stats, save_settings, save_stats
from .constants import APP_DISPLAY_NAME, asset_path, format_mmss
from .timer_state import ReminderClock
from .windows import BreakPromptWindow, BreakWindow, DashboardDialog, SettingsDialog


class EyeBreakController(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.settings = load_settings()
        self.stats = load_stats()
        self.is_started = not self.settings.start_paused
        self.is_paused = self.settings.start_paused
        self.is_waiting_break_confirmation = False
        self.is_on_break = False
        self.work_clock = ReminderClock(self.settings.work_minutes * 60)
        self.break_clock = ReminderClock(self.settings.break_seconds)
        self.work_remaining = self.work_clock.remaining_seconds
        self.break_remaining = self.break_clock.remaining_seconds
        self.dashboard_dialog: DashboardDialog | None = None

        self.work_timer = QTimer(self)
        self.work_timer.setInterval(1000)
        self.work_timer.timeout.connect(self._tick_work)

        self.break_timer = QTimer(self)
        self.break_timer.setInterval(1000)
        self.break_timer.timeout.connect(self._tick_break)

        self.prompt_window = self._make_prompt_window(fullscreen=False)
        self.fullscreen_prompt_window = self._make_prompt_window(fullscreen=True)
        self.popup_window = self._make_break_window(fullscreen=False)
        self.fullscreen_window = self._make_break_window(fullscreen=True)

        self.tray = QSystemTrayIcon(self._app_icon(), self.app)
        self.tray.setToolTip(self._tooltip())
        self.tray.setContextMenu(self._build_menu())
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        if self.is_started and not self.is_paused:
            self.work_clock.start()
            self.work_timer.start()
        else:
            QTimer.singleShot(300, self.open_dashboard)
        self._refresh_menu()

    def _make_prompt_window(self, *, fullscreen: bool) -> BreakPromptWindow:
        window = BreakPromptWindow(self.settings, fullscreen=fullscreen)
        window.start_requested.connect(self.begin_break_countdown)
        window.skipped.connect(self.skip_break)
        window.snoozed.connect(lambda: self.snooze(minutes=self.settings.snooze_minutes))
        return window

    def _make_break_window(self, *, fullscreen: bool) -> BreakWindow:
        window = BreakWindow(self.settings, fullscreen=fullscreen)
        window.skipped.connect(self.skip_break)
        window.completed_early.connect(self.complete_break)
        return window

    def _app_icon(self) -> QIcon:
        icon = QIcon(asset_path("assets/icon.svg"))
        if icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        return icon

    def _build_menu(self) -> QMenu:
        self.menu = QMenu()
        self.countdown_action = QAction("倒计时：--:--")
        self.countdown_action.setEnabled(False)

        self.start_action = QAction("开始")
        self.start_action.triggered.connect(self.start_or_resume)

        self.pause_action = QAction("暂停")
        self.pause_action.triggered.connect(self.toggle_pause)

        self.start_break_action = QAction("立即休息")
        self.start_break_action.triggered.connect(lambda: self.request_break(manual=True))

        self.reset_action = QAction("重置计时")
        self.reset_action.triggered.connect(self.reset_work_timer)

        self.dashboard_action = QAction("控制面板/今日统计")
        self.dashboard_action.triggered.connect(self.open_dashboard)

        self.settings_action = QAction("设置")
        self.settings_action.triggered.connect(self.open_settings)

        self.about_action = QAction("关于")
        self.about_action.triggered.connect(self.show_about)

        self.quit_action = QAction("退出")
        self.quit_action.triggered.connect(self.quit)

        self.menu.addAction(self.countdown_action)
        self.menu.addSeparator()
        self.menu.addAction(self.start_action)
        self.menu.addAction(self.pause_action)
        self.menu.addAction(self.start_break_action)
        self.menu.addAction(self.reset_action)
        self.menu.addSeparator()
        self.menu.addAction(self.dashboard_action)
        self.menu.addAction(self.settings_action)
        self.menu.addAction(self.about_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        return self.menu

    def _refresh_menu(self) -> None:
        self.countdown_action.setText(self._countdown_menu_text())
        if self.is_waiting_break_confirmation:
            self.start_action.setText(f"开始休息{self.settings.break_seconds}秒")
            self.start_action.setEnabled(True)
        elif not self.is_started:
            self.start_action.setText("开始")
            self.start_action.setEnabled(True)
        elif self.is_paused:
            self.start_action.setText("继续")
            self.start_action.setEnabled(True)
        else:
            self.start_action.setText("正在计时")
            self.start_action.setEnabled(False)

        self.pause_action.setText("继续" if self.is_paused else "暂停")
        self.pause_action.setEnabled(self.is_started and not self.is_on_break and not self.is_waiting_break_confirmation)
        self.start_break_action.setEnabled(self.is_started and not self.is_on_break and not self.is_waiting_break_confirmation)
        self.reset_action.setEnabled(not self.is_on_break and not self.is_waiting_break_confirmation)
        self.tray.setToolTip(self._tooltip())
        if self.dashboard_dialog is not None:
            self.dashboard_dialog.refresh()

    def _countdown_menu_text(self) -> str:
        if self.is_on_break:
            return f"休息倒计时：{self.break_remaining}s"
        if self.is_waiting_break_confirmation:
            return "用眼倒计时：00:00，请开始休息"
        if not self.is_started:
            return f"用眼倒计时：{format_mmss(self.settings.work_minutes * 60)}"
        return f"用眼倒计时：{format_mmss(self.work_remaining)}"

    def _tooltip(self) -> str:
        if self.is_on_break:
            return f"{APP_DISPLAY_NAME}: 正在休息，还剩{self.break_remaining}秒"
        if self.is_waiting_break_confirmation:
            return f"{APP_DISPLAY_NAME}: 20分钟已到，请开始休息"
        if not self.is_started:
            return f"{APP_DISPLAY_NAME}: 未开始，点击开始进入20分钟计时"
        if self.is_paused:
            return f"{APP_DISPLAY_NAME}: 已暂停，剩余{format_mmss(self.work_remaining)}"
        return f"{APP_DISPLAY_NAME}: 距离下次休息还有{format_mmss(self.work_remaining)}"

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.is_waiting_break_confirmation:
                self._show_prompt_window()
            elif self.is_on_break:
                self._show_break_window()
            else:
                self.open_dashboard()

    def start_or_resume(self) -> None:
        if self.is_on_break:
            return
        if self.is_waiting_break_confirmation:
            self.begin_break_countdown()
            return
        if not self.is_started:
            self.is_started = True
            self.is_paused = False
            self.work_clock.reset(self.settings.work_minutes * 60, start=True)
            self.work_remaining = self.work_clock.remaining_seconds
            self.work_timer.start()
            self.tray.showMessage(
                APP_DISPLAY_NAME,
                f"已开始{self.settings.work_minutes}分钟用眼计时。",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
        elif self.is_paused:
            self.is_paused = False
            self.work_clock.start()
            self.work_timer.start()
        self._refresh_menu()

    def _tick_work(self) -> None:
        if self.is_paused or self.is_on_break or self.is_waiting_break_confirmation or not self.is_started:
            return
        self.work_remaining = self.work_clock.update()
        if self.work_remaining <= 0:
            self.request_break()
            return
        self._refresh_menu()

    def _tick_break(self) -> None:
        self.break_remaining = self.break_clock.update()
        self._update_break_windows()
        self._refresh_menu()
        if self.break_remaining <= 0:
            self.complete_break()

    def _update_break_windows(self) -> None:
        self.popup_window.update_countdown(self.break_remaining)
        self.fullscreen_window.update_countdown(self.break_remaining)

    def _record_focus_length(self) -> None:
        focus_minutes = round(self.work_clock.elapsed_seconds / 60)
        if focus_minutes > self.stats.longest_focus_minutes:
            self.stats.longest_focus_minutes = focus_minutes
            save_stats(self.stats)

    def request_break(self, *, manual: bool = False) -> None:
        if self.is_on_break or self.is_waiting_break_confirmation:
            return
        self.work_timer.stop()
        self.work_remaining = self.work_clock.pause()
        self.is_started = True
        self.is_paused = False
        self.is_waiting_break_confirmation = True
        self._record_focus_length()

        if self.settings.enable_sound:
            QApplication.beep()
        if self.settings.enable_notifications:
            title = "202020Reminder提醒"
            message = (
                f"{'手动休息：' if manual else '20分钟到了：'}"
                f"请看向{self.settings.distance_text}，点击开始后休息{self.settings.break_seconds}秒。"
            )
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 6000)

        self._show_prompt_window()
        self._refresh_menu()

    def _show_prompt_window(self) -> None:
        if self.settings.enable_fullscreen:
            self.fullscreen_prompt_window.open_prompt()
        elif self.settings.enable_popup:
            self.prompt_window.open_prompt()

    def begin_break_countdown(self) -> None:
        if self.is_on_break:
            return
        self._hide_prompt_windows()
        self.is_waiting_break_confirmation = False
        self.is_on_break = True
        self.break_clock.reset(self.settings.break_seconds, start=True)
        self.break_remaining = self.break_clock.remaining_seconds

        if self.settings.enable_sound:
            QApplication.beep()
        if self.settings.enable_notifications:
            self.tray.showMessage(
                APP_DISPLAY_NAME,
                f"休息开始：请看向{self.settings.distance_text}，保持{self.settings.break_seconds}秒。",
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )
        self._show_break_window()
        self.break_timer.start()
        self._refresh_menu()

    def _show_break_window(self) -> None:
        if self.settings.enable_fullscreen:
            self.fullscreen_window.start(self.settings.break_seconds)
        elif self.settings.enable_popup:
            self.popup_window.start(self.settings.break_seconds)

    def complete_break(self) -> None:
        if not self.is_on_break:
            return
        self.break_remaining = self.break_clock.update()
        elapsed_rest_seconds = max(1, self.break_clock.elapsed_seconds)
        if self.break_remaining <= 0:
            elapsed_rest_seconds = self.break_clock.duration_seconds
        self.break_timer.stop()
        self.break_clock.pause()
        self._hide_break_windows()
        self.is_on_break = False
        self.stats.completed_breaks += 1
        self.stats.total_rest_seconds += elapsed_rest_seconds
        save_stats(self.stats)

        start_next = self._show_break_completed_prompt()
        self.reset_work_timer(start=start_next)
        if start_next:
            self.is_started = True
            self.is_paused = False
            self.work_timer.start()
        else:
            self.is_started = True
            self.is_paused = True
            self.work_timer.stop()
        self._refresh_menu()

    def _show_break_completed_prompt(self) -> bool:
        if self.settings.enable_sound:
            QApplication.beep()
        if self.settings.enable_notifications:
            self.tray.showMessage(
                APP_DISPLAY_NAME,
                "20秒休息完成，可以开始下一轮用眼计时。",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

        box = QMessageBox()
        box.setWindowTitle("休息完成")
        box.setText("20秒休息完成。")
        box.setInformativeText(f"点击“开始下一轮”后，将重新进入{self.settings.work_minutes}分钟用眼计时。")
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        start_button = box.addButton("开始下一轮", QMessageBox.ButtonRole.AcceptRole)
        pause_button = box.addButton("先暂停", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(start_button)
        box.exec()
        return box.clickedButton() != pause_button

    def skip_break(self) -> None:
        if not self.is_on_break and not self.is_waiting_break_confirmation:
            return
        self.break_timer.stop()
        self._hide_prompt_windows()
        self._hide_break_windows()
        self.is_on_break = False
        self.is_waiting_break_confirmation = False
        self.stats.skipped_breaks += 1
        save_stats(self.stats)
        self.reset_work_timer(start=True)
        self.is_started = True
        self.is_paused = False
        self.work_timer.start()
        self._refresh_menu()

    def snooze(self, minutes: int = 1) -> None:
        if not self.is_on_break and not self.is_waiting_break_confirmation:
            return
        self.break_timer.stop()
        self._hide_prompt_windows()
        self._hide_break_windows()
        self.is_on_break = False
        self.is_waiting_break_confirmation = False
        self.stats.snoozed_breaks += 1
        save_stats(self.stats)
        self.work_clock.reset(max(1, minutes * 60), start=True)
        self.work_remaining = self.work_clock.remaining_seconds
        self.is_started = True
        self.is_paused = False
        self.work_timer.start()
        self._refresh_menu()

    def _hide_prompt_windows(self) -> None:
        self.prompt_window.hide()
        self.fullscreen_prompt_window.hide()

    def _hide_break_windows(self) -> None:
        self.popup_window.hide()
        self.fullscreen_window.hide()

    def reset_work_timer(self, start: bool = True) -> None:
        self.work_clock.reset(self.settings.work_minutes * 60, start=start)
        self.work_remaining = self.work_clock.remaining_seconds
        self.tray.setToolTip(self._tooltip())
        if start:
            self.is_started = True
            self.is_paused = False
            self.work_timer.start()
        else:
            self.work_timer.stop()
        self._refresh_menu()

    def toggle_pause(self) -> None:
        if self.is_on_break or self.is_waiting_break_confirmation:
            return
        if not self.is_started:
            self.start_or_resume()
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.work_remaining = self.work_clock.pause()
            self.work_timer.stop()
        else:
            self.work_clock.start()
            self.work_timer.start()
        self._refresh_menu()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.to_settings()
            save_settings(self.settings)
            self._recreate_windows()
            if not self.is_on_break and not self.is_waiting_break_confirmation:
                self.reset_work_timer(start=self.is_started and not self.is_paused)
            self._refresh_menu()
            self.tray.showMessage("202020Reminder", "设置已保存。", QSystemTrayIcon.MessageIcon.Information, 2500)

    def _recreate_windows(self) -> None:
        self._hide_prompt_windows()
        self._hide_break_windows()
        self.prompt_window.deleteLater()
        self.fullscreen_prompt_window.deleteLater()
        self.popup_window.deleteLater()
        self.fullscreen_window.deleteLater()
        self.prompt_window = self._make_prompt_window(fullscreen=False)
        self.fullscreen_prompt_window = self._make_prompt_window(fullscreen=True)
        self.popup_window = self._make_break_window(fullscreen=False)
        self.fullscreen_window = self._make_break_window(fullscreen=True)

    def open_dashboard(self) -> None:
        self.stats = load_stats()
        if self.dashboard_dialog is None:
            self.dashboard_dialog = DashboardDialog(self)
            self.dashboard_dialog.finished.connect(lambda *_args: setattr(self, "dashboard_dialog", None))
        self.dashboard_dialog.refresh()
        self.dashboard_dialog.show()
        self.dashboard_dialog.raise_()
        self.dashboard_dialog.activateWindow()

    def show_about(self) -> None:
        QMessageBox.about(
            None,
            "关于202020Reminder",
            (
                "202020Reminder是一款基于20-20-20法则的Windows护眼提醒工具。\n\n"
                "推荐流程：点击开始 → 自动计时20分钟 → 确认开始休息 → 休息20秒 → 提示完成并进入下一轮。\n"
                "支持右下角轻提示、小弹窗置顶和全屏遮罩三种提醒方式。\n"
                "开源、轻量、无广告、无登录、无数据收集。"
            ),
        )

    def quit(self) -> None:
        self.break_timer.stop()
        self.work_timer.stop()
        self._hide_prompt_windows()
        self._hide_break_windows()
        self.tray.hide()
        self.app.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setWindowIcon(QIcon(asset_path("assets/icon.svg")))
    app.setQuitOnLastWindowClosed(False)

    # Let Ctrl+C in a development terminal close the app cleanly instead of printing a scary traceback.
    try:
        signal.signal(signal.SIGINT, lambda *_args: app.quit())
    except (ValueError, AttributeError):
        # Some embedded or frozen environments may not allow signal handlers.
        pass

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_DISPLAY_NAME, "当前系统不支持系统托盘，程序无法常驻运行。")
        return 1

    _controller = EyeBreakController(app)
    try:
        return app.exec()
    except KeyboardInterrupt:
        # Friendly exit when running from PowerShell / Windows Terminal during development.
        return 0
