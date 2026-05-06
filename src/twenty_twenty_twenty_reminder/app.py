from __future__ import annotations

import signal
import sys
from importlib.resources import files

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .config import DailyStats, Settings, load_settings, load_stats, save_settings, save_stats

APP_DISPLAY_NAME = "202020Reminder"
APP_SUBTITLE = "20-20-20 Eye Break Reminder"
DEFAULT_DISTANCE_TEXT = "20英尺/约6米以外"


def asset_path(relative_path: str) -> str:
    return str(files("twenty_twenty_twenty_reminder").joinpath(relative_path))


def format_mmss(total_seconds: int) -> str:
    minutes, seconds = divmod(max(0, total_seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"


class BreakPromptWindow(QWidget):
    """Ask the user to explicitly start the 20-second eye break.

    The app does not start the break countdown immediately when the 20-minute
    focus period ends. It first asks for confirmation, which makes the flow less
    surprising and avoids counting a break while the user is still finishing a task.
    """

    start_requested = Signal()
    skipped = Signal()
    snoozed = Signal()

    def __init__(self, settings: Settings, *, fullscreen: bool = False) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if settings.always_on_top or fullscreen:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.settings = settings
        self.fullscreen = fullscreen

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setObjectName("promptWindow")
        self.setMinimumWidth(540 if not fullscreen else 780)
        self.setStyleSheet(
            """
            QWidget#promptWindow {
                background: #eef6ff;
                border: 1px solid #c7d2fe;
                border-radius: 18px;
            }
            QLabel#brand {
                font-size: 12px;
                letter-spacing: 1px;
                color: #64748b;
            }
            QLabel#title {
                font-size: 28px;
                font-weight: 800;
            }
            QLabel#tip {
                font-size: 15px;
                color: #475569;
            }
            QPushButton {
                padding: 10px 18px;
                border-radius: 9px;
            }
            QPushButton#primaryButton {
                font-weight: 700;
            }
            """
        )

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            """
            QFrame#card {
                background: white;
                border-radius: 24px;
                border: 1px solid #dbeafe;
            }
            """
        )
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(34, 30, 34, 30)
        main_layout.setSpacing(16)

        brand = QLabel("20 · 20 · 20")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("20分钟到了，准备休息一下")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tip = QLabel(
            f"点击“开始休息”后，程序会进入{settings.break_seconds}秒倒计时。"
            f"请看向{settings.distance_text}的物体，并让眼睛自然眨动。"
        )
        tip.setObjectName("tip")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setWordWrap(True)

        self.start_button = QPushButton(f"开始休息{settings.break_seconds}秒")
        self.start_button.setObjectName("primaryButton")
        self.snooze_button = QPushButton(f"稍后{settings.snooze_minutes}分钟")
        self.skip_button = QPushButton("跳过本次")
        self.start_button.clicked.connect(self.start_requested.emit)
        self.snooze_button.clicked.connect(self.snoozed.emit)
        self.skip_button.clicked.connect(self.skipped.emit)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch(1)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.snooze_button)
        button_layout.addWidget(self.skip_button)
        button_layout.addStretch(1)

        hint = QLabel("确认开始后才会统计为休息，避免在你还没离开屏幕时误计时。")
        hint.setObjectName("tip")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)

        main_layout.addWidget(brand)
        main_layout.addWidget(title)
        main_layout.addWidget(tip)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(hint)

        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(18, 18, 18, 18)
        if fullscreen:
            wrapper.addStretch(1)
            wrapper.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
            wrapper.addStretch(1)
        else:
            wrapper.addWidget(card)

    def open_prompt(self) -> None:
        if self.fullscreen:
            self.showFullScreen()
        else:
            self._move_to_center()
            self.show()
        self.raise_()
        self.activateWindow()

    def _move_to_center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.adjustSize()
        x = geometry.x() + (geometry.width() - self.width()) // 2
        y = geometry.y() + (geometry.height() - self.height()) // 2
        self.move(x, y)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()
        self.snoozed.emit()


class BreakWindow(QWidget):
    skipped = Signal()
    completed_early = Signal()

    def __init__(self, settings: Settings, *, fullscreen: bool = False) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if settings.always_on_top or fullscreen:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.settings = settings
        self.fullscreen = fullscreen
        self.total_seconds = settings.break_seconds
        self.remaining_seconds = settings.break_seconds

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setObjectName("breakWindow")
        self.setMinimumWidth(520 if not fullscreen else 760)
        self.setStyleSheet(
            """
            QWidget#breakWindow {
                background: #f8fafc;
                border: 1px solid #d9d9d9;
                border-radius: 18px;
            }
            QLabel#brand {
                font-size: 12px;
                letter-spacing: 1px;
                color: #64748b;
            }
            QLabel#title {
                font-size: 28px;
                font-weight: 800;
            }
            QLabel#tip {
                font-size: 15px;
                color: #475569;
            }
            QLabel#countdown {
                font-size: 56px;
                font-weight: 900;
            }
            QPushButton {
                padding: 9px 16px;
                border-radius: 9px;
            }
            QProgressBar {
                min-height: 12px;
                border-radius: 6px;
                text-align: center;
            }
            """
        )

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            """
            QFrame#card {
                background: white;
                border-radius: 24px;
                border: 1px solid #e2e8f0;
            }
            """
        )
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(34, 30, 34, 30)
        main_layout.setSpacing(16)

        brand = QLabel("20 · 20 · 20")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("正在休息眼睛")
        self.title_label.setObjectName("title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.tip_label = QLabel(f"请看向{settings.distance_text}的物体，慢慢眨眼，让眼睛放松。")
        self.tip_label.setObjectName("tip")
        self.tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tip_label.setWordWrap(True)

        self.countdown_label = QLabel()
        self.countdown_label.setObjectName("countdown")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, settings.break_seconds)
        self.progress_bar.setTextVisible(False)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        self.done_button = QPushButton("我已完成")
        self.skip_button = QPushButton("跳过休息")
        self.done_button.clicked.connect(self.completed_early.emit)
        self.skip_button.clicked.connect(self.skipped.emit)
        button_layout.addStretch(1)
        button_layout.addWidget(self.done_button)
        button_layout.addWidget(self.skip_button)
        button_layout.addStretch(1)

        self.done_hint = QLabel("20秒结束后会提示你开始下一轮计时 · No login, no ads, no tracking")
        self.done_hint.setObjectName("tip")
        self.done_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(brand)
        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.tip_label)
        main_layout.addWidget(self.countdown_label)
        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.done_hint)

        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(18, 18, 18, 18)
        if fullscreen:
            wrapper.addStretch(1)
            wrapper.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
            wrapper.addStretch(1)
        else:
            wrapper.addWidget(card)
        self.update_countdown(settings.break_seconds)

    def start(self, total_seconds: int) -> None:
        self.total_seconds = total_seconds
        self.remaining_seconds = total_seconds
        self.progress_bar.setRange(0, total_seconds)
        self.update_countdown(total_seconds)
        if self.fullscreen:
            self.showFullScreen()
        else:
            self._move_to_center()
            self.show()
        self.raise_()
        self.activateWindow()

    def update_countdown(self, remaining_seconds: int) -> None:
        self.remaining_seconds = max(0, remaining_seconds)
        self.countdown_label.setText(f"{self.remaining_seconds}s")
        self.progress_bar.setValue(self.total_seconds - self.remaining_seconds)

    def _move_to_center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.adjustSize()
        x = geometry.x() + (geometry.width() - self.width()) // 2
        y = geometry.y() + (geometry.height() - self.height()) // 2
        self.move(x, y)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()
        self.skipped.emit()


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("202020Reminder设置")
        self.setMinimumWidth(460)

        self.work_minutes = QSpinBox()
        self.work_minutes.setRange(1, 180)
        self.work_minutes.setSuffix("分钟")
        self.work_minutes.setValue(settings.work_minutes)

        self.break_seconds = QSpinBox()
        self.break_seconds.setRange(5, 600)
        self.break_seconds.setSuffix("秒")
        self.break_seconds.setValue(settings.break_seconds)

        self.snooze_minutes = QSpinBox()
        self.snooze_minutes.setRange(1, 30)
        self.snooze_minutes.setSuffix("分钟")
        self.snooze_minutes.setValue(settings.snooze_minutes)

        self.distance_text = QLineEdit(settings.distance_text)

        self.enable_sound = QCheckBox("休息开始/结束时播放提示音")
        self.enable_sound.setChecked(settings.enable_sound)

        self.enable_notifications = QCheckBox("右下角轻提示/系统托盘通知")
        self.enable_notifications.setChecked(settings.enable_notifications)

        self.enable_popup = QCheckBox("小弹窗置顶提醒")
        self.enable_popup.setChecked(settings.enable_popup)

        self.enable_fullscreen = QCheckBox("全屏遮罩提醒")
        self.enable_fullscreen.setChecked(settings.enable_fullscreen)

        self.always_on_top = QCheckBox("提醒窗口置顶")
        self.always_on_top.setChecked(settings.always_on_top)

        self.start_paused = QCheckBox("启动后先等待点击开始")
        self.start_paused.setChecked(settings.start_paused)

        reminder_mode_tip = QLabel("提醒方式可多选；若全部关闭，程序会自动保留“小弹窗置顶提醒”。")
        reminder_mode_tip.setWordWrap(True)
        reminder_mode_tip.setStyleSheet("color: #64748b;")

        flow_tip = QLabel("交互流程：开始计时 → 20分钟后确认开始休息 → 20秒倒计时 → 提示休息完成 → 下一轮。")
        flow_tip.setWordWrap(True)
        flow_tip.setStyleSheet("color: #64748b;")

        form = QFormLayout()
        form.addRow("用眼时长", self.work_minutes)
        form.addRow("休息时长", self.break_seconds)
        form.addRow("稍后提醒", self.snooze_minutes)
        form.addRow("眺望距离提示", self.distance_text)
        form.addRow(self.enable_sound)
        form.addRow(self.enable_notifications)
        form.addRow(self.enable_popup)
        form.addRow(self.enable_fullscreen)
        form.addRow(self.always_on_top)
        form.addRow(self.start_paused)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(reminder_mode_tip)
        layout.addWidget(flow_tip)
        layout.addWidget(buttons)

    def to_settings(self) -> Settings:
        return Settings.from_dict(
            {
                "work_minutes": self.work_minutes.value(),
                "break_seconds": self.break_seconds.value(),
                "snooze_minutes": self.snooze_minutes.value(),
                "distance_text": self.distance_text.text().strip() or DEFAULT_DISTANCE_TEXT,
                "enable_sound": self.enable_sound.isChecked(),
                "enable_notifications": self.enable_notifications.isChecked(),
                "enable_popup": self.enable_popup.isChecked(),
                "enable_fullscreen": self.enable_fullscreen.isChecked(),
                "always_on_top": self.always_on_top.isChecked(),
                "start_paused": self.start_paused.isChecked(),
            }
        )


class DashboardDialog(QDialog):
    def __init__(self, controller: "EyeBreakController", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle(f"控制面板 - {APP_DISPLAY_NAME} v0.4.1")
        self.setMinimumWidth(560)
        # QDialog 在 Windows 上默认更像“对话框”，部分环境不会显示最小化按钮。
        # 这里显式使用标准 Window 标题栏，并启用系统菜单、最小化按钮和关闭按钮。
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        title = QLabel("今天的20-20-20完成情况")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")

        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 14px; color: #334155;")
        self.next_label = QLabel()
        self.next_label.setStyleSheet("font-size: 14px; color: #2563eb;")
        self.next_label.setWordWrap(True)

        self.countdown_title = QLabel("本轮用眼倒计时")
        self.countdown_title.setStyleSheet("font-size: 13px; color: #64748b;")
        self.countdown_value = QLabel()
        self.countdown_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_value.setStyleSheet("font-size: 42px; font-weight: 900; color: #0f172a;")

        self.countdown_bar = QProgressBar()
        self.countdown_bar.setTextVisible(False)
        self.countdown_bar.setMinimumHeight(12)

        self.day_value = QLabel()
        self.completed_value = QLabel()
        self.skipped_value = QLabel()
        self.snoozed_value = QLabel()
        self.rest_value = QLabel()
        self.rate_value = QLabel()
        self.focus_value = QLabel()

        form = QFormLayout()
        form.addRow("当前状态", self.status_label)
        form.addRow("下一步", self.next_label)
        form.addRow("日期", self.day_value)
        form.addRow("已完成休息", self.completed_value)
        form.addRow("跳过休息", self.skipped_value)
        form.addRow("稍后提醒", self.snoozed_value)
        form.addRow("累计休息", self.rest_value)
        form.addRow("完成率", self.rate_value)
        form.addRow("最长连续用眼", self.focus_value)

        self.start_button = QPushButton("开始")
        self.pause_button = QPushButton("暂停")
        self.break_now_button = QPushButton("立即休息")
        self.reset_button = QPushButton("重置计时")
        minimize_button = QPushButton("最小化到任务栏")
        close_button = QPushButton("隐藏到托盘")

        self.start_button.clicked.connect(self.controller.start_or_resume)
        self.pause_button.clicked.connect(self.controller.toggle_pause)
        self.break_now_button.clicked.connect(lambda: self.controller.request_break(manual=True))
        self.reset_button.clicked.connect(self.controller.reset_work_timer)
        minimize_button.clicked.connect(self.showMinimized)
        close_button.clicked.connect(self.close)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.break_now_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch(1)
        button_layout.addWidget(minimize_button)
        button_layout.addWidget(close_button)

        note = QLabel("点击“开始”后自动进入20分钟用眼计时；右上角“-”或底部“最小化到任务栏”会最小化控制面板；“隐藏到托盘”和右上角X只隐藏窗口，计时继续运行。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b;")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.countdown_title)
        layout.addWidget(self.countdown_value)
        layout.addWidget(self.countdown_bar)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addLayout(button_layout)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()
        self.refresh()

    def refresh(self) -> None:
        stats = self.controller.stats
        rest_minutes, rest_seconds = divmod(stats.total_rest_seconds, 60)
        rate = f"{stats.completion_rate * 100:.0f}%" if stats.completed_breaks + stats.skipped_breaks else "--"

        work_total = self.controller.settings.work_minutes * 60
        break_total = self.controller.settings.break_seconds

        if self.controller.is_on_break:
            status = "正在休息"
            next_step = f"请看向远处，休息倒计时{self.controller.break_remaining}秒。"
            countdown_title = "休息倒计时"
            countdown_text = f"{self.controller.break_remaining}s"
            progress_total = max(1, break_total)
            progress_value = progress_total - max(0, self.controller.break_remaining)
            start_text = "休息中"
            start_enabled = False
            pause_enabled = False
            break_enabled = False
        elif self.controller.is_waiting_break_confirmation:
            status = "等待开始休息"
            next_step = "20分钟已到，请点击提醒窗口中的“开始休息”，或在这里点击“开始”。"
            countdown_title = "本轮用眼倒计时"
            countdown_text = "00:00"
            progress_total = max(1, work_total)
            progress_value = progress_total
            start_text = f"开始休息{self.controller.settings.break_seconds}秒"
            start_enabled = True
            pause_enabled = False
            break_enabled = False
        elif not self.controller.is_started:
            status = "未开始"
            next_step = f"点击“开始”后进入{self.controller.settings.work_minutes}分钟用眼计时。"
            countdown_title = "本轮用眼倒计时"
            countdown_text = format_mmss(work_total)
            progress_total = max(1, work_total)
            progress_value = 0
            start_text = "开始"
            start_enabled = True
            pause_enabled = False
            break_enabled = False
        elif self.controller.is_paused:
            status = "已暂停"
            next_step = f"剩余{format_mmss(self.controller.work_remaining)}，点击“继续”恢复计时。"
            countdown_title = "本轮用眼倒计时"
            countdown_text = format_mmss(self.controller.work_remaining)
            progress_total = max(1, work_total)
            progress_value = progress_total - max(0, self.controller.work_remaining)
            start_text = "继续"
            start_enabled = True
            pause_enabled = False
            break_enabled = True
        else:
            status = "正在计时"
            next_step = f"距离下次护眼提醒还有{format_mmss(self.controller.work_remaining)}。"
            countdown_title = "本轮用眼倒计时"
            countdown_text = format_mmss(self.controller.work_remaining)
            progress_total = max(1, work_total)
            progress_value = progress_total - max(0, self.controller.work_remaining)
            start_text = "正在计时"
            start_enabled = False
            pause_enabled = True
            break_enabled = True

        self.countdown_title.setText(countdown_title)
        self.countdown_value.setText(countdown_text)
        self.countdown_bar.setRange(0, progress_total)
        self.countdown_bar.setValue(progress_value)
        self.status_label.setText(status)
        self.next_label.setText(next_step)
        self.day_value.setText(stats.day)
        self.completed_value.setText(f"{stats.completed_breaks}次")
        self.skipped_value.setText(f"{stats.skipped_breaks}次")
        self.snoozed_value.setText(f"{stats.snoozed_breaks}次")
        self.rest_value.setText(f"{rest_minutes}分{rest_seconds}秒")
        self.rate_value.setText(rate)
        self.focus_value.setText(f"约{stats.longest_focus_minutes}分钟")

        self.start_button.setText(start_text)
        self.start_button.setEnabled(start_enabled)
        self.pause_button.setEnabled(pause_enabled)
        self.break_now_button.setEnabled(break_enabled)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Hide the dashboard instead of stopping the background reminder."""
        event.ignore()
        self.hide()
        if self.controller.tray.isVisible():
            self.controller.tray.showMessage(
                APP_DISPLAY_NAME,
                "控制面板已隐藏到托盘，计时会继续运行。",
                QSystemTrayIcon.MessageIcon.Information,
                1800,
            )


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
        self.work_remaining = self.settings.work_minutes * 60
        self.break_remaining = self.settings.break_seconds
        self.focus_elapsed_seconds = 0
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
            self.work_remaining = self.settings.work_minutes * 60
            self.focus_elapsed_seconds = 0
            self.work_timer.start()
            self.tray.showMessage(
                APP_DISPLAY_NAME,
                f"已开始{self.settings.work_minutes}分钟用眼计时。",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
        elif self.is_paused:
            self.is_paused = False
            self.work_timer.start()
        self._refresh_menu()

    def _tick_work(self) -> None:
        if self.is_paused or self.is_on_break or self.is_waiting_break_confirmation or not self.is_started:
            return
        self.work_remaining -= 1
        self.focus_elapsed_seconds += 1
        if self.work_remaining <= 0:
            self.request_break()
            return
        self._refresh_menu()

    def _tick_break(self) -> None:
        self.break_remaining -= 1
        self._update_break_windows()
        self._refresh_menu()
        if self.break_remaining <= 0:
            self.complete_break()

    def _update_break_windows(self) -> None:
        self.popup_window.update_countdown(self.break_remaining)
        self.fullscreen_window.update_countdown(self.break_remaining)

    def _record_focus_length(self) -> None:
        focus_minutes = round(self.focus_elapsed_seconds / 60)
        if focus_minutes > self.stats.longest_focus_minutes:
            self.stats.longest_focus_minutes = focus_minutes
            save_stats(self.stats)

    def request_break(self, *, manual: bool = False) -> None:
        if self.is_on_break or self.is_waiting_break_confirmation:
            return
        self.work_timer.stop()
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
        self.break_remaining = self.settings.break_seconds

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
        elapsed_rest_seconds = max(1, self.settings.break_seconds - max(0, self.break_remaining))
        if self.break_remaining <= 0:
            elapsed_rest_seconds = self.settings.break_seconds
        self.break_timer.stop()
        self._hide_break_windows()
        self.is_on_break = False
        self.stats.completed_breaks += 1
        self.stats.total_rest_seconds += elapsed_rest_seconds
        save_stats(self.stats)
        self.focus_elapsed_seconds = 0

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
        self.focus_elapsed_seconds = 0
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
        self.work_remaining = max(1, minutes * 60)
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
        self.work_remaining = self.settings.work_minutes * 60
        self.focus_elapsed_seconds = 0
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
            self.work_timer.stop()
        else:
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
