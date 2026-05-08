from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
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
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .config import Settings
from .constants import APP_DISPLAY_NAME, APP_VERSION, DEFAULT_DISTANCE_TEXT, format_mmss

if TYPE_CHECKING:
    from .app import EyeBreakController

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
        self.setWindowTitle(f"控制面板 - {APP_DISPLAY_NAME} v{APP_VERSION}")
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

