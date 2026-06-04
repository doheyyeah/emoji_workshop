import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QFrame, QScrollArea, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon, QFont, QColor, QFontMetrics

# Matplotlib 嵌入 PyQt6
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.database_service import DatabaseService
from utils.config_manager import ConfigManager


class StatsPanel(QWidget):
    """数据统计面板：核心指标 + 趋势图 + 时段分布 + Top10

    保留指标：
    - 总图片数 / 总标签数 / 总使用次数（紧凑小卡片，占幅较小）
    - 每日使用趋势折线图（最近7天）
    - 使用时段分布图（最近24小时滚动窗口）
    - 最常用 Top10 表情（列表 + 缩略图）

    整个面板内容包裹在可滚动区域中，保证图表标题不被裁剪、可拖拽查看。
    时间统一使用本地时间，精确到分钟。
    """

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.config = ConfigManager()
        self.thumb_service = None  # 延迟导入避免循环
        # 记录最近一次刷新「最近7天趋势」时所属的日期，用于跨天（24:00）时同步刷新
        self._last_trend_date = datetime.now().date()
        self.setup_ui()
        self.refresh_stats()

    def setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # === 顶部标题 + 刷新按钮 ===
        header_layout = QHBoxLayout()
        title_label = QLabel("📊 数据统计")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px 0;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        self.refresh_button = QPushButton("🔄 刷新")
        self.refresh_button.setToolTip("刷新「使用时段分布（最近24小时）」；跨天时同时刷新「最近7天使用趋势」")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        header_layout.addWidget(self.refresh_button)
        outer_layout.addLayout(header_layout)

        # === 可滚动内容区域（保证图表始终可查看、标题不被裁剪）===
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer_layout.addWidget(self.scroll_area)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 2, 2)

        # === 三个核心数字卡片（紧凑、占幅小）===
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(6)
        self.card_images = self._make_card("总图片数", "0")
        self.card_tags = self._make_card("总标签数", "0")
        self.card_usage = self._make_card("总使用次数", "0")
        cards_layout.addWidget(self.card_images)
        cards_layout.addWidget(self.card_tags)
        cards_layout.addWidget(self.card_usage)
        layout.addLayout(cards_layout)

        # === 每日使用趋势（最近7天）===
        layout.addWidget(QLabel("📈 最近 7 天使用趋势"))
        self.trend_figure = Figure(figsize=(7, 2.8), dpi=90)
        self.trend_figure.patch.set_facecolor('#1e1e1e')
        self.trend_canvas = FigureCanvas(self.trend_figure)
        self.trend_canvas.setMinimumHeight(200)
        layout.addWidget(self.trend_canvas)

        # === 时段分布图（最近24小时）===
        layout.addWidget(QLabel("⏰ 使用时段分布（最近 24 小时）"))
        self.hour_figure = Figure(figsize=(7, 2.8), dpi=90)
        self.hour_figure.patch.set_facecolor('#1e1e1e')
        self.hour_canvas = FigureCanvas(self.hour_figure)
        self.hour_canvas.setMinimumHeight(200)
        layout.addWidget(self.hour_canvas)

        # === 最常用 Top10 ===
        layout.addWidget(QLabel("🏆 最常用 Top 10 表情"))
        self.top10_list = QListWidget()
        self.top10_list.setMinimumHeight(220)
        layout.addWidget(self.top10_list)

        # === 最近刷新时间 ===
        self.refresh_label = QLabel("")
        self.refresh_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.refresh_label)

        layout.addStretch()
        self.scroll_area.setWidget(content)

    def _make_card(self, title: str, value: str) -> QFrame:
        """创建紧凑统计数字卡片（占幅较小）"""
        card = QFrame()
        card.setObjectName("statsCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        card.setMinimumHeight(56)
        card.setMaximumHeight(72)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(2)
        title_lbl = AutoFitLabel(title, min_size=9, max_size=12)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("color: #aaa;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_lbl = AutoFitLabel(value, min_size=12, max_size=22)
        value_lbl.setStyleSheet("color: #4a9eff; font-weight: bold;")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title_lbl, 1)
        v.addWidget(value_lbl, 1)
        # 保存 value_lbl 引用以便更新
        card._title_label = title_lbl
        card._value_label = value_lbl
        return card

    def on_refresh_clicked(self):
        """刷新按钮：更新「最近24小时」时段分布；跨天时同步刷新「最近7天趋势」与卡片"""
        self._refresh_cards()
        self._refresh_hourly()
        # 跨天（例如到了次日 00:00）时，最近7天的窗口已经滚动，需要同步刷新
        if datetime.now().date() != self._last_trend_date:
            self._refresh_trend()
        self._refresh_top10()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.refresh_label.setText(f"上次刷新：{now_str}")

    def refresh_stats(self):
        """刷新所有统计数据（使用本地时间）"""
        self._refresh_cards()
        self._refresh_trend()
        self._refresh_hourly()
        self._refresh_top10()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.refresh_label.setText(f"上次刷新：{now_str}")

    def _refresh_cards(self):
        """更新三张核心卡片"""
        stats = self.db.get_stats()
        image_count = stats.get("count", 0)
        tags = self.db.get_all_tags()
        tag_count = len(tags)

        # 使用次数（来自 usage_history）
        try:
            usage_rows = self.db.get_usage_history()
            usage_count = len(usage_rows)
        except Exception:
            usage_count = 0

        self.card_images._value_label.setText(str(image_count))
        self.card_tags._value_label.setText(str(tag_count))
        self.card_usage._value_label.setText(str(usage_count))

    @staticmethod
    def _parse_used_at(used_at_str: str) -> datetime | None:
        """解析 used_at 时间字符串，兼容多种格式（YYYY-MM-DDTHH:MM:SS.ffffff / YYYY-MM-DD HH:MM:SS）"""
        try:
            s = str(used_at_str).replace('T', ' ').split('.')[0]
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None

    def _refresh_trend(self):
        """最近7天使用趋势折线图（本地时间）"""
        self.trend_figure.clear()
        ax = self.trend_figure.add_subplot(111)
        ax.set_facecolor('#1e1e1e')
        ax.tick_params(colors='white', labelsize=8)
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')

        # 生成最近7天的日期列表
        today = datetime.now().date()
        dates = [(today - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
        counts = defaultdict(int)

        try:
            rows = self.db.get_usage_history()
            for row in rows:
                # row: (id, image_id, used_at)
                dt = self._parse_used_at(row[2])
                try:
                    if dt is None:
                        continue
                    day_label = dt.date().strftime("%m-%d")
                    if day_label in dates:
                        counts[day_label] += 1
                except ValueError:
                    pass
        except Exception:
            pass

        values = [counts.get(d, 0) for d in dates]
        ax.plot(dates, values, marker='o', color='#4a9eff', linewidth=2, markersize=5)
        ax.fill_between(dates, values, alpha=0.2, color='#4a9eff')
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates)
        for spine in ax.spines.values():
            spine.set_color('#3e3e42')
        # 标题由上方 QLabel 提供，此处仅留出充足边距，避免顶部被裁剪
        self.trend_figure.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.18)
        self.trend_canvas.draw()
        # 记录本次趋势刷新所属日期，用于跨天检测
        self._last_trend_date = today

    def _refresh_hourly(self):
        """最近24小时时段分布柱状图（本地时间，滚动窗口）

        仅统计从当前时刻往前倒 24 小时内的使用记录，按小时（0-23）归类，
        以便实时反映用户「最近这一天」的活跃时段。
        """
        self.hour_figure.clear()
        ax = self.hour_figure.add_subplot(111)
        ax.set_facecolor('#1e1e1e')
        ax.tick_params(colors='white', labelsize=8)

        now = datetime.now()
        window_start = now - timedelta(hours=24)
        hour_counts = [0] * 24
        try:
            rows = self.db.get_usage_history()
            for row in rows:
                dt = self._parse_used_at(row[2])
                if dt is not None and window_start <= dt <= now:
                    hour_counts[dt.hour] += 1
        except Exception:
            pass

        hours = list(range(24))
        colors = ['#4a9eff' if h in range(9, 22) else '#3a6ea8' for h in hours]
        ax.bar(hours, hour_counts, color=colors, edgecolor='none')
        ax.set_xticks(range(0, 24, 3))
        ax.set_xticklabels([f"{h}时" for h in range(0, 24, 3)], color='white', fontsize=8)
        for spine in ax.spines.values():
            spine.set_color('#3e3e42')
        # 标题由上方 QLabel 提供，此处仅留出充足边距，避免顶部被裁剪
        self.hour_figure.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.18)
        self.hour_canvas.draw()

    def _refresh_top10(self):
        """最常用 Top10 表情（带缩略图）

        排名逻辑：按累计使用次数从高到低排序后取前 10 名，依次编号 #1…#N。
        若被使用过的表情不足 10 张，则展示全部（#1…#N）；否则只展示最多的 10 张。
        """
        self.top10_list.clear()
        self.top10_list.setIconSize(QSize(40, 40))
        try:
            rows = self.db.get_usage_history()
        except Exception:
            return

        if not rows:
            self.top10_list.addItem("暂无使用记录")
            return

        # 统计每张图片的使用次数
        use_counts: dict = defaultdict(int)
        for row in rows:
            image_id = row[1]
            use_counts[image_id] += 1

        # 按使用次数降序排序后取前 10（不足 10 张则全部展示），依次编号 #1…#N
        ranked = sorted(use_counts.items(), key=lambda x: (-x[1], x[0]))[:10]

        # 延迟导入 ThumbnailService
        if self.thumb_service is None:
            from services.thumbnail_service import ThumbnailService
            self.thumb_service = ThumbnailService()

        rank = 0
        for image_id, count in ranked:
            img_row = self.db.get_image_by_id(image_id)
            if not img_row:
                continue
            rank += 1
            name = img_row[1]
            file_path = img_row[2]

            item = QListWidgetItem(f"#{rank:<2d}  {name}   ·   使用 {count} 次")
            item.setData(Qt.ItemDataRole.UserRole, image_id)

            # 加载缩略图
            thumb_path = self.thumb_service.get_thumbnail(file_path)
            if thumb_path:
                pixmap = QPixmap(thumb_path)
            else:
                pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(40, 40,
                                       Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(scaled))

            self.top10_list.addItem(item)


class AutoFitLabel(QLabel):
    """根据当前控件尺寸自动调整字号，避免文本被裁剪"""

    def __init__(self, text: str = "", min_size: int = 10, max_size: int = 36, parent=None):
        super().__init__(text, parent)
        self._min_size = min_size
        self._max_size = max_size
        self._update_font()

    def setText(self, text: str):
        super().setText(text)
        self._update_font()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_font()

    def _update_font(self):
        text = self.text() or " "
        rect = self.contentsRect()
        max_w = max(10, rect.width() - 6)
        max_h = max(10, rect.height() - 6)
        font = self.font()
        flags = int(self.alignment())
        if self.wordWrap():
            flags |= int(Qt.TextFlag.TextWordWrap)
        for size in range(self._max_size, self._min_size - 1, -1):
            font.setPointSize(size)
            metrics = QFontMetrics(font)
            text_rect = metrics.boundingRect(0, 0, max_w, max_h, flags, text)
            if text_rect.height() <= max_h and text_rect.width() <= max_w:
                self.setFont(font)
                return
        font.setPointSize(self._min_size)
        self.setFont(font)
