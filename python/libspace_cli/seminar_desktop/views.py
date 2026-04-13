from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
    from PySide6.QtCore import QEasingCurve, QEvent, Qt, QVariantAnimation, Signal
    from PySide6.QtGui import QColor, QPainter, QRadialGradient, QShowEvent
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QFrame,
        QGraphicsDropShadowEffect,
        QGridLayout,
        QHeaderView,
        QHBoxLayout,
        QLabel,
        QLayout,
        QLineEdit,
        QPlainTextEdit,
        QScrollArea,
        QSizePolicy,
        QTextEdit,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    from qfluentwidgets import (
        BodyLabel,
        CaptionLabel,
        CardWidget,
        FluentIcon as FIF,
        LargeTitleLabel,
        PrimaryPushButton,
        PushButton,
        StrongBodyLabel,
        SubtitleLabel,
        SwitchButton,
    )

from .models import DiscoverSnapshot, SeminarGuiFormData
from .service import resolve_discover_room_status


ACCENT_COLOR = QColor("#0078D4")


def _set_layout_margins(layout: QLayout, margins: int | tuple[int, int, int, int], spacing: int) -> None:
    if isinstance(margins, int):
        layout.setContentsMargins(margins, margins, margins, margins)
    else:
        layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)


def _clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


class StatusChip(QLabel):
    def __init__(self, text: str, *, accent: bool = False, warning: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("statusChip")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(28)
        if warning:
            background = "rgba(255, 166, 43, 38)"
            border = "rgba(255, 166, 43, 110)"
            foreground = "#FFC95E"
        elif accent:
            background = "rgba(0, 120, 212, 48)"
            border = "rgba(0, 120, 212, 140)"
            foreground = "#E8F3FF"
        else:
            background = "rgba(255, 255, 255, 22)"
            border = "rgba(255, 255, 255, 44)"
            foreground = "#D8E6F5"
        self.setStyleSheet(
            f"""
            QLabel#statusChip {{
                background: {background};
                color: {foreground};
                border: 1px solid {border};
                border-radius: 14px;
                padding: 4px 12px;
                font: 600 10pt 'Microsoft YaHei UI';
            }}
            """
        )


class PremiumCard(CardWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("premiumCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._hover_progress = 0.0
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(34)
        self._shadow.setOffset(0, 18)
        self._shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(self._shadow)

        self._hover_animation = QVariantAnimation(self)
        self._hover_animation.setDuration(240)
        self._hover_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._hover_animation.valueChanged.connect(self._apply_hover_state)
        self._apply_hover_state(0.0)

    def enterEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def _animate_hover(self, end_value: float) -> None:
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(end_value)
        self._hover_animation.start()

    def _apply_hover_state(self, value: float) -> None:
        self._hover_progress = float(value)
        blur = 34 + 18 * self._hover_progress
        offset = 18 + 10 * self._hover_progress
        alpha = 180 + int(24 * self._hover_progress)
        border_alpha = 22 + int(58 * self._hover_progress)
        self._shadow.setBlurRadius(blur)
        self._shadow.setOffset(0, offset)
        self._shadow.setColor(QColor(0, 0, 0, alpha))
        self.setStyleSheet(
            f"""
            CardWidget#premiumCard {{
                background: rgba(18, 24, 31, 228);
                border: 1px solid rgba(255, 255, 255, {border_alpha});
                border-radius: 26px;
            }}
            """
        )


class FocusShell(QFrame):
    def __init__(self, field: QWidget, *, minimum_height: int = 56, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focusShell")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(minimum_height)
        self._field = field
        self._progress = 0.0

        field.installEventFilter(self)
        field.setObjectName("shellField")

        layout = QVBoxLayout(self)
        _set_layout_margins(layout, (18, 12, 18, 12), 0)
        layout.addWidget(field)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(28)
        self._shadow.setOffset(0, 10)
        self._shadow.setColor(QColor(0, 0, 0, 110))
        self.setGraphicsEffect(self._shadow)

        self._animation = QVariantAnimation(self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.valueChanged.connect(self._apply_progress)
        self._apply_progress(0.0)

    @property
    def field(self) -> QWidget:
        return self._field

    def eventFilter(self, watched, event) -> bool:
        if watched is self._field and event.type() == QEvent.FocusIn:
            self._animate_to(1.0)
        elif watched is self._field and event.type() == QEvent.FocusOut:
            self._animate_to(0.0)
        return super().eventFilter(watched, event)

    def _animate_to(self, value: float) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(value)
        self._animation.start()

    def _apply_progress(self, value: float) -> None:
        self._progress = float(value)
        border_alpha = 38 + int(120 * self._progress)
        glow_alpha = 10 + int(74 * self._progress)
        self._shadow.setBlurRadius(28 + 12 * self._progress)
        self._shadow.setOffset(0, 10 + 6 * self._progress)
        self._shadow.setColor(QColor(ACCENT_COLOR.red(), ACCENT_COLOR.green(), ACCENT_COLOR.blue(), glow_alpha))
        self.setStyleSheet(
            f"""
            QFrame#focusShell {{
                background: rgba(10, 15, 20, 168);
                border: 1px solid rgba({ACCENT_COLOR.red()}, {ACCENT_COLOR.green()}, {ACCENT_COLOR.blue()}, {border_alpha});
                border-radius: 18px;
            }}
            """
        )


class AuroraPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._opacity = 1.0
        self._opacity_animation = QVariantAnimation(self)
        self._opacity_animation.setDuration(280)
        self._opacity_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._opacity_animation.valueChanged.connect(self._set_page_opacity)

    def showEvent(self, event: QShowEvent) -> None:
        self._opacity_animation.stop()
        self._opacity_animation.setStartValue(0.0)
        self._opacity_animation.setEndValue(1.0)
        self._opacity_animation.start()
        super().showEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#05080D"))

        orb_1 = QRadialGradient(self.width() * 0.8, self.height() * 0.15, self.width() * 0.35)
        orb_1.setColorAt(0.0, QColor(ACCENT_COLOR.red(), ACCENT_COLOR.green(), ACCENT_COLOR.blue(), 70))
        orb_1.setColorAt(1.0, QColor(ACCENT_COLOR.red(), ACCENT_COLOR.green(), ACCENT_COLOR.blue(), 0))
        painter.fillRect(self.rect(), orb_1)

        orb_2 = QRadialGradient(self.width() * 0.2, self.height() * 0.9, self.width() * 0.45)
        orb_2.setColorAt(0.0, QColor(255, 255, 255, 24))
        orb_2.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), orb_2)

        if self._opacity < 1.0:
            painter.fillRect(self.rect(), QColor(5, 8, 13, int((1.0 - self._opacity) * 180)))

        super().paintEvent(event)

    def _set_page_opacity(self, value: float) -> None:
        self._opacity = float(value)
        self.update()


class RoomCard(PremiumCard):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        _set_layout_margins(layout, 22, 12)

        self.title_label = SubtitleLabel("", self)
        self.meta_label = CaptionLabel("", self)
        self.window_label = StrongBodyLabel("", self)
        self.capacity_label = BodyLabel("", self)
        self.blocked_label = CaptionLabel("", self)
        self.days_label = CaptionLabel("", self)
        self.upload_chip = StatusChip("可自动尝试", accent=True, parent=self)

        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)
        layout.addSpacing(4)
        layout.addWidget(self.window_label)
        layout.addWidget(self.capacity_label)
        layout.addWidget(self.blocked_label)
        layout.addWidget(self.days_label)
        layout.addSpacing(8)
        layout.addWidget(self.upload_chip, alignment=Qt.AlignLeft)

    def bind(self, room) -> None:
        self.title_label.setText(room.label)
        self.meta_label.setText(f"roomId {room.room_id}  |  容量 {room.member_count}")
        self.window_label.setText(room.time_window)
        self.capacity_label.setText(f"人数要求：{room.participant_range}")
        self.blocked_label.setText(f"禁用时段：{room.blocked_ranges}")
        self.days_label.setText(f"可预约日期：{room.available_days}")
        replacement = StatusChip("需上传材料", warning=True, parent=self) if room.upload_required else StatusChip("可自动尝试", accent=True, parent=self)
        layout = self.layout()
        layout.replaceWidget(self.upload_chip, replacement)
        self.upload_chip.deleteLater()
        self.upload_chip = replacement


class FloorSectionBanner(PremiumCard):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        _set_layout_margins(layout, (20, 16, 20, 16), 12)
        self.title_label = StrongBodyLabel("", self)
        self.detail_label = CaptionLabel("", self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.detail_label)
        layout.addStretch(1)

    def bind(self, floor_name: str, room_count: int) -> None:
        self.title_label.setText(floor_name)
        self.detail_label.setText(f"{room_count} rooms")


class DashboardPage(AuroraPage):
    discover_requested = Signal()
    reserve_now_requested = Signal()
    reserve_wait_requested = Signal()
    save_requested = Signal()
    open_txt_requested = Signal()
    open_doc_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        _set_layout_margins(root, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("pageScrollArea")
        root.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        content = QVBoxLayout(container)
        _set_layout_margins(content, (36, 32, 36, 120), 22)

        hero = PremiumCard(container)
        hero_layout = QVBoxLayout(hero)
        _set_layout_margins(hero_layout, 28, 10)

        chip_row = QHBoxLayout()
        _set_layout_margins(chip_row, (0, 0, 0, 0), 10)
        chip_row.addWidget(StatusChip("仅允许预约当天", accent=True, parent=hero))
        chip_row.addWidget(StatusChip(f"结束时间不得晚于 22:30", parent=hero))
        chip_row.addStretch(1)

        self.hero_title = LargeTitleLabel("独立研讨室预约系统", hero)
        self.hero_subtitle = CaptionLabel(
            "以 Fluent 桌面体验重构预约流程：主账号登录、房间优先队列、到点自动提交、TXT 摘要输出。",
            hero,
        )

        hero_layout.addLayout(chip_row)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_subtitle)
        content.addWidget(hero)

        stats_row = QHBoxLayout()
        _set_layout_margins(stats_row, (0, 0, 0, 0), 18)
        self.account_card = self._create_summary_card("主账号状态", "等待输入统一身份认证账号", "未检测到本地认证信息。")
        self.room_card = self._create_summary_card("房间策略", "尚未配置 roomId 优先列表", "推荐先获取今日空闲后再选择。")
        self.topic_card = self._create_summary_card("预约主题", "尚未填写主题和时间", "系统只支持预约当天。")
        stats_row.addWidget(self.account_card)
        stats_row.addWidget(self.room_card)
        stats_row.addWidget(self.topic_card)
        content.addLayout(stats_row)

        action_card = PremiumCard(container)
        action_layout = QVBoxLayout(action_card)
        _set_layout_margins(action_layout, 24, 16)
        action_layout.addWidget(SubtitleLabel("即时操作", action_card))
        action_layout.addWidget(CaptionLabel("保存配置、导出今日空闲、立即预约或等待到点自动提交。", action_card))

        button_row = QHBoxLayout()
        _set_layout_margins(button_row, (0, 0, 0, 0), 12)
        self.save_button = PushButton("保存配置", action_card)
        self.save_button.setIcon(FIF.SAVE)
        self.discover_button = PushButton("获取今日空闲", action_card)
        self.discover_button.setIcon(FIF.SEARCH)
        self.reserve_now_button = PrimaryPushButton("立即预约", action_card)
        self.reserve_now_button.setIcon(FIF.PLAY)
        self.reserve_wait_button = PushButton("到点预约", action_card)
        self.reserve_wait_button.setIcon(FIF.HISTORY)
        self.settings_button = PushButton("偏好设置", action_card)
        self.settings_button.setIcon(FIF.SETTING)
        for button in (
            self.save_button,
            self.discover_button,
            self.reserve_now_button,
            self.reserve_wait_button,
            self.settings_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch(1)

        utility_row = QHBoxLayout()
        _set_layout_margins(utility_row, (0, 0, 0, 0), 12)
        self.open_txt_button = PushButton("打开 TXT 摘要", action_card)
        self.open_txt_button.setIcon(FIF.DOCUMENT)
        self.open_txt_button.setEnabled(False)
        self.open_doc_button = PushButton("打开 roomId 对照表", action_card)
        self.open_doc_button.setIcon(FIF.FOLDER)
        self.busy_chip = StatusChip("空闲", parent=action_card)
        utility_row.addWidget(self.open_txt_button)
        utility_row.addWidget(self.open_doc_button)
        utility_row.addStretch(1)
        utility_row.addWidget(self.busy_chip)

        action_layout.addLayout(button_row)
        action_layout.addLayout(utility_row)
        content.addWidget(action_card)

        results_card = PremiumCard(container)
        results_layout = QVBoxLayout(results_card)
        _set_layout_margins(results_layout, 24, 16)
        self.results_title = SubtitleLabel("今日空闲研讨室", results_card)
        self.results_meta = CaptionLabel("点击“获取今日空闲”后，会同步生成 JSON 和 TXT 摘要。", results_card)
        self.results_tree = QTreeWidget(results_card)
        self.results_tree.setObjectName("resultsTree")
        self.results_tree.setColumnCount(6)
        self.results_tree.setHeaderLabels(["楼层 / 房间", "roomId", "人数", "禁用时段", "可约日期", "状态"])
        self.results_tree.setRootIsDecorated(True)
        self.results_tree.setUniformRowHeights(True)
        self.results_tree.setAnimated(False)
        self.results_tree.setIndentation(18)
        self.results_tree.setFocusPolicy(Qt.NoFocus)
        self.results_tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.results_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.results_tree.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.results_tree.setMinimumHeight(520)
        self.results_tree.setAlternatingRowColors(False)
        results_header = self.results_tree.header()
        results_header.setStretchLastSection(False)
        results_header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 6):
            results_header.setSectionResizeMode(column, QHeaderView.Interactive)
        self.results_tree.setColumnWidth(1, 96)
        self.results_tree.setColumnWidth(2, 110)
        self.results_tree.setColumnWidth(3, 280)
        self.results_tree.setColumnWidth(4, 150)
        self.results_tree.setColumnWidth(5, 120)
        self.results_empty = BodyLabel("尚未加载今日空闲房间。", results_card)
        self.results_empty.setObjectName("emptyStateLabel")

        results_layout.addWidget(self.results_title)
        results_layout.addWidget(self.results_meta)
        results_layout.addWidget(self.results_empty)
        results_layout.addWidget(self.results_tree)
        self.results_tree.hide()
        content.addWidget(results_card)
        content.addStretch(1)

        self.save_button.clicked.connect(self.save_requested)
        self.discover_button.clicked.connect(self.discover_requested)
        self.reserve_now_button.clicked.connect(self.reserve_now_requested)
        self.reserve_wait_button.clicked.connect(self.reserve_wait_requested)
        self.open_txt_button.clicked.connect(self.open_txt_requested)
        self.open_doc_button.clicked.connect(self.open_doc_requested)
        self.settings_button.clicked.connect(self.settings_requested)

    def _create_summary_card(self, title: str, headline: str, subtitle: str) -> PremiumCard:
        card = PremiumCard(self)
        layout = QVBoxLayout(card)
        _set_layout_margins(layout, 22, 8)
        layout.addWidget(CaptionLabel(title, card))
        lead = SubtitleLabel(headline, card)
        detail = BodyLabel(subtitle, card)
        detail.setWordWrap(True)
        layout.addWidget(lead)
        layout.addWidget(detail)
        card.lead_label = lead  # type: ignore[attr-defined]
        card.detail_label = detail  # type: ignore[attr-defined]
        return card

    def set_form_summary(self, form: SeminarGuiFormData) -> None:
        if form.username:
            masked = f"{form.username[:4]}****{form.username[-2:]}" if len(form.username) >= 6 else form.username
            self.account_card.lead_label.setText(f"主账号已就绪：{masked}")  # type: ignore[attr-defined]
            self.account_card.detail_label.setText("预约链路只使用主账号登录，其他参与人仅解析学号。")  # type: ignore[attr-defined]
        else:
            self.account_card.lead_label.setText("等待输入统一身份认证账号")  # type: ignore[attr-defined]
            self.account_card.detail_label.setText("如果本地没有账号信息，可直接在偏好设置中录入。")  # type: ignore[attr-defined]

        room_ids = [item for item in form.priority_room_ids_text.replace(",", "\n").splitlines() if item.strip()]
        if room_ids:
            preview = " · ".join(room_ids[:4])
            suffix = " ..." if len(room_ids) > 4 else ""
            self.room_card.lead_label.setText(f"优先队列：{preview}{suffix}")  # type: ignore[attr-defined]
            self.room_card.detail_label.setText("未指定 roomId 时，系统会按此顺序自动优选。")  # type: ignore[attr-defined]
        else:
            self.room_card.lead_label.setText("尚未配置 roomId 优先列表")  # type: ignore[attr-defined]
            self.room_card.detail_label.setText("没有优先队列时无法在 GUI 中发起预约。")  # type: ignore[attr-defined]

        if form.title and form.start_time and form.end_time:
            self.topic_card.lead_label.setText(f"{form.title}  |  {form.start_time}-{form.end_time}")  # type: ignore[attr-defined]
            self.topic_card.detail_label.setText("超过 4 小时会自动拆成两段请求，且总时长不超过 8 小时。")  # type: ignore[attr-defined]
        else:
            self.topic_card.lead_label.setText("尚未填写主题和时间")  # type: ignore[attr-defined]
            self.topic_card.detail_label.setText("只支持预约当天，且结束时间不能晚于 22:30。")  # type: ignore[attr-defined]

    def set_snapshot(self, snapshot: DiscoverSnapshot | None) -> None:
        self.results_tree.setUpdatesEnabled(False)
        self.results_tree.clear()
        if snapshot is None or not snapshot.rooms:
            self.results_empty.setVisible(True)
            self.results_empty.setText("尚未加载今日空闲房间。")
            self.results_meta.setText("点击“获取今日空闲”后，会同步生成 JSON 和 TXT 摘要。")
            self.open_txt_button.setEnabled(False)
            self.results_tree.hide()
            self.results_tree.setUpdatesEnabled(True)
            return

        self.results_empty.setVisible(False)
        self.results_tree.show()
        txt_path_text = str(snapshot.txt_path) if snapshot.txt_path is not None else "未生成"
        self.results_meta.setText(
            f"目标日期：{snapshot.target_date}  |  楼层数：{len({room.floor_name or '未分层' for room in snapshot.rooms})}  |  房间数：{len(snapshot.rooms)}  |  TXT 摘要：{txt_path_text}"
        )
        self.open_txt_button.setEnabled(snapshot.txt_path is not None and snapshot.txt_path.exists())
        floor_names: list[str] = []
        grouped_rooms: dict[str, list] = {}
        for room in snapshot.rooms:
            floor_name = room.floor_name or "未分层"
            if floor_name not in grouped_rooms:
                grouped_rooms[floor_name] = []
                floor_names.append(floor_name)
            grouped_rooms[floor_name].append(room)

        for floor_name in floor_names:
            floor_rooms = grouped_rooms[floor_name]
            floor_item = QTreeWidgetItem(
                [
                    f"{floor_name} ({len(floor_rooms)} 间)",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            floor_font = floor_item.font(0)
            floor_font.setBold(True)
            floor_item.setFont(0, floor_font)
            self.results_tree.addTopLevelItem(floor_item)
            for room in floor_rooms:
                status_text = resolve_discover_room_status(room, target_date=snapshot.target_date)
                child = QTreeWidgetItem(
                    [
                        room.label,
                        room.room_id,
                        room.participant_range,
                        room.blocked_ranges,
                        room.available_days,
                        status_text,
                    ]
                )
                floor_item.addChild(child)
            floor_item.setExpanded(True)
        self.results_tree.setUpdatesEnabled(True)

    def set_busy(self, busy: bool, busy_text: str) -> None:
        for button in (
            self.save_button,
            self.discover_button,
            self.reserve_now_button,
            self.reserve_wait_button,
            self.settings_button,
        ):
            button.setEnabled(not busy)

        replacement = StatusChip(busy_text or "空闲", accent=busy, parent=self)
        parent_layout = self.busy_chip.parentWidget().layout()
        parent_layout.replaceWidget(self.busy_chip, replacement)
        self.busy_chip.deleteLater()
        self.busy_chip = replacement


class SettingsPage(AuroraPage):
    save_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        _set_layout_margins(root, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("pageScrollArea")
        root.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        content = QVBoxLayout(container)
        _set_layout_margins(content, (36, 32, 36, 120), 22)

        header_card = PremiumCard(container)
        header_layout = QVBoxLayout(header_card)
        _set_layout_margins(header_layout, 26, 10)
        header_layout.addWidget(LargeTitleLabel("偏好设置", header_card))
        header_layout.addWidget(
            CaptionLabel("这里只填写账号、手机号、房间优先顺序、参与人和主题内容。日期输入已被移除，系统固定只能预约当天。", header_card)
        )
        content.addWidget(header_card)

        auth_card = PremiumCard(container)
        auth_layout = QGridLayout(auth_card)
        _set_layout_margins(auth_layout, 24, 14)
        auth_layout.addWidget(SubtitleLabel("身份认证与联系信息", auth_card), 0, 0, 1, 2)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("统一身份认证账号")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("统一身份认证密码")
        self.mobile_edit = QLineEdit()
        self.mobile_edit.setPlaceholderText("手机号")
        auth_layout.addWidget(self._field_block("账号", self.username_edit), 1, 0)
        auth_layout.addWidget(self._field_block("密码", self.password_edit), 1, 1)
        auth_layout.addWidget(self._field_block("手机号", self.mobile_edit), 2, 0, 1, 2)
        content.addWidget(auth_card)

        strategy_card = PremiumCard(container)
        strategy_layout = QGridLayout(strategy_card)
        _set_layout_margins(strategy_layout, 24, 14)
        strategy_layout.addWidget(SubtitleLabel("预约策略", strategy_card), 0, 0, 1, 2)

        self.trigger_edit = QLineEdit()
        self.trigger_edit.setPlaceholderText("HH:MM:SS，例如 08:00:00")
        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText("HH:MM，例如 08:00")
        self.end_edit = QLineEdit()
        self.end_edit.setPlaceholderText("HH:MM，且不得晚于 22:30")
        self.public_switch = SwitchButton()
        self.public_switch.setChecked(True)

        strategy_layout.addWidget(self._field_block("触发时间", self.trigger_edit), 1, 0)
        strategy_layout.addWidget(self._field_block("开始时间", self.start_edit), 1, 1)
        strategy_layout.addWidget(self._field_block("结束时间", self.end_edit), 2, 0)
        strategy_layout.addWidget(self._switch_block("公开预约", self.public_switch), 2, 1)

        self.room_ids_edit = QTextEdit()
        self.room_ids_edit.setPlaceholderText("一行一个 roomId，或用逗号分隔。\n只填一个 roomId 就是固定预约该房间。")
        self.room_ids_edit.setMinimumHeight(132)
        strategy_layout.addWidget(self._field_block("roomId 优先顺序", self.room_ids_edit, tall=True), 3, 0, 1, 2)
        content.addWidget(strategy_card)

        seminar_card = PremiumCard(container)
        seminar_layout = QGridLayout(seminar_card)
        _set_layout_margins(seminar_layout, 24, 14)
        seminar_layout.addWidget(SubtitleLabel("研讨内容与成员", seminar_card), 0, 0, 1, 2)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("研讨主题")
        self.participants_edit = QTextEdit()
        self.participants_edit.setPlaceholderText("一行一个参与人学号，或用逗号分隔。\n不要把主账号本人写进去。")
        self.participants_edit.setMinimumHeight(132)
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("填写网页预约中的内容说明。")
        self.content_edit.setMinimumHeight(180)

        seminar_layout.addWidget(self._field_block("主题", self.title_edit), 1, 0, 1, 2)
        seminar_layout.addWidget(self._field_block("参与人学号", self.participants_edit, tall=True), 2, 0)
        seminar_layout.addWidget(self._field_block("研讨内容", self.content_edit, tall=True), 2, 1)

        footer_row = QHBoxLayout()
        _set_layout_margins(footer_row, (0, 0, 0, 0), 12)
        footer_row.addWidget(StatusChip("系统只支持预约当天", accent=True, parent=seminar_card))
        footer_row.addWidget(StatusChip("图书馆 22:30 关闭", warning=True, parent=seminar_card))
        footer_row.addStretch(1)
        self.save_button = PrimaryPushButton("保存偏好设置", seminar_card)
        self.save_button.setIcon(FIF.SAVE)
        footer_row.addWidget(self.save_button)
        seminar_layout.addLayout(footer_row, 3, 0, 1, 2)
        content.addWidget(seminar_card)
        content.addStretch(1)

        self.save_button.clicked.connect(self.save_requested)

    def _field_block(self, title: str, field: QWidget, *, tall: bool = False):
        container = QWidget(self)
        layout = QVBoxLayout(container)
        _set_layout_margins(layout, (0, 0, 0, 0), 8)
        layout.addWidget(CaptionLabel(title, container))
        shell = FocusShell(field, minimum_height=148 if tall else 56, parent=container)
        if isinstance(field, (QTextEdit, QPlainTextEdit)):
            field.setFrameStyle(QFrame.NoFrame)
        layout.addWidget(shell)
        return container

    def _switch_block(self, title: str, switch: SwitchButton):
        container = QWidget(self)
        layout = QVBoxLayout(container)
        _set_layout_margins(layout, (0, 0, 0, 0), 8)
        layout.addWidget(CaptionLabel(title, container))

        shell = FocusShell(QWidget(container), minimum_height=56, parent=container)
        inner_layout = QHBoxLayout(shell.field)
        _set_layout_margins(inner_layout, (0, 0, 0, 0), 12)
        inner_layout.addWidget(BodyLabel("提交网页表单中的“是否公开”字段", shell))
        inner_layout.addStretch(1)
        inner_layout.addWidget(switch)
        layout.addWidget(shell)
        return container

    def bind_form(self, form: SeminarGuiFormData) -> None:
        self.username_edit.setText(form.username)
        self.password_edit.setText(form.password)
        self.mobile_edit.setText(form.mobile)
        self.trigger_edit.setText(form.trigger_time)
        self.start_edit.setText(form.start_time)
        self.end_edit.setText(form.end_time)
        self.title_edit.setText(form.title)
        self.participants_edit.setPlainText(form.participants_text)
        self.room_ids_edit.setPlainText(form.priority_room_ids_text)
        self.content_edit.setPlainText(form.content)
        self.public_switch.setChecked(form.open_value != "0")

    def collect_form(self) -> SeminarGuiFormData:
        return SeminarGuiFormData(
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            trigger_time=self.trigger_edit.text().strip(),
            start_time=self.start_edit.text().strip(),
            end_time=self.end_edit.text().strip(),
            participants_text=self.participants_edit.toPlainText().strip(),
            priority_room_ids_text=self.room_ids_edit.toPlainText().strip(),
            title=self.title_edit.text().strip(),
            content=self.content_edit.toPlainText().strip(),
            mobile=self.mobile_edit.text().strip(),
            open_value="1" if self.public_switch.isChecked() else "0",
        )

    def set_busy(self, busy: bool) -> None:
        self.save_button.setEnabled(not busy)


class LogLineCard(PremiumCard):
    def __init__(self, line: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        _set_layout_margins(layout, 18, 6)
        timestamp, _, rest = line.partition(" [")
        title = StrongBodyLabel(timestamp if rest else "运行日志", self)
        body = CaptionLabel(line if not rest else f"[{rest}", self)
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)


class LogsPage(AuroraPage):
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        _set_layout_margins(root, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("pageScrollArea")
        root.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        content = QVBoxLayout(container)
        _set_layout_margins(content, (36, 32, 36, 120), 18)

        header = PremiumCard(container)
        header_layout = QHBoxLayout(header)
        _set_layout_margins(header_layout, 24, 16)
        title_box = QVBoxLayout()
        _set_layout_margins(title_box, (0, 0, 0, 0), 6)
        title_box.addWidget(LargeTitleLabel("运行日志", header))
        title_box.addWidget(CaptionLabel("底部抽拉控制台用于实时反馈，这里保留最近的结构化日志快照。", header))
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)
        self.refresh_button = PushButton("刷新日志", header)
        self.refresh_button.setIcon(FIF.SYNC)
        header_layout.addWidget(self.refresh_button)
        content.addWidget(header)

        self.log_console = QPlainTextEdit(container)
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(620)
        content.addWidget(self.log_console)
        content.addStretch(1)
        self.refresh_button.clicked.connect(self.refresh_requested)

    def set_logs(self, lines: list[str]) -> None:
        if not lines:
            self.log_console.setPlainText("暂无运行日志。")
            return

        self.log_console.setPlainText("\n".join(reversed(lines[-120:])))

    def set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)


class LogDrawer(QFrame):
    height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("logDrawer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._expanded = False
        self._collapsed_height = 0
        self._expanded_height = 320
        self.setMaximumHeight(self._collapsed_height)
        self.setMinimumHeight(self._collapsed_height)
        self.hide()

        layout = QVBoxLayout(self)
        _set_layout_margins(layout, (20, 18, 20, 18), 12)
        header = QHBoxLayout()
        _set_layout_margins(header, (0, 0, 0, 0), 12)
        header.addWidget(StrongBodyLabel("沉浸式日志控制台", self))
        self.status_label = CaptionLabel("等待操作", self)
        header.addWidget(self.status_label)
        header.addStretch(1)
        layout.addLayout(header)

        self.console = QPlainTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(0)
        self.console.setMaximumHeight(220)
        self.console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.console)

        self._animation = QVariantAnimation(self)
        self._animation.setDuration(260)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.valueChanged.connect(self._apply_height)
        self._animation.finished.connect(self._sync_visibility)

    @property
    def overlay_height(self) -> int:
        if not self.isVisible():
            return 0
        return self.maximumHeight()

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        start = self.maximumHeight() if self.isVisible() else self._collapsed_height
        self._expanded = not self._expanded
        end = self._expanded_height if self._expanded else self._collapsed_height
        if self._expanded:
            self.show()
            self.raise_()
        self._animation.stop()
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()
        self.height_changed.emit()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_lines(self, lines: list[str]) -> None:
        self.console.setPlainText("\n".join(lines[-120:]))
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def append_line(self, text: str) -> None:
        if not text.strip():
            return
        self.console.appendPlainText(text.rstrip())
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def _apply_height(self, value: float) -> None:
        height = int(value)
        self.setMaximumHeight(height)
        self.setMinimumHeight(height)
        self.height_changed.emit()

    def _sync_visibility(self) -> None:
        if not self._expanded and self.maximumHeight() <= self._collapsed_height:
            self.hide()
        elif self._expanded:
            self.show()
        self.height_changed.emit()
