import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QFrame
)
from PyQt6.QtCore import Qt
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
    - 总图片数 / 总标签数 / 总使用次数（三张卡片）
    - 每日使用趋势折线图（最近7天）
    - 使用时段分布图（24小时柱状图）
    - 最常用 Top10 表情（列表 + 缩略图）

    时间统一使用本地时间，精确到分钟。
    """

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.config = ConfigManager()
        self.thumb_service = None  # 延迟导入避免循环
        self.setup_ui()
        self.refresh_stats()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # === 顶部标题 ===
        title_label = QLabel("📊 数据统计")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px 0;")
        layout.addWidget(title_label)

        # === 三个核心数字卡片 ===
        cards_layout = QHBoxLayout()
        self.card_images = self._make_card("总图片数", "0")
        self.card_tags = self._make_card("总标签数", "0")
        self.card_usage = self._make_card("总使用次数", "0")
        cards_layout.addWidget(self.card_images)
        cards_layout.addWidget(self.card_tags)
        cards_layout.addWidget(self.card_usage)
        layout.addLayout(cards_layout)

        # === 每日使用趋势（最近7天）===
        self.trend_figure = Figure(figsize=(7, 2.5), dpi=90)
        self.trend_figure.patch.set_facecolor('#1e1e1e')
        self.trend_canvas = FigureCanvas(self.trend_figure)
        layout.addWidget(QLabel("📈 最近 7 天使用趋势"))
        layout.addWidget(self.trend_canvas)

        # === 时段分布图（24小时）===
        self.hour_figure = Figure(figsize=(7, 2.5), dpi=90)
        self.hour_figure.patch.set_facecolor('#1e1e1e')
        self.hour_canvas = FigureCanvas(self.hour_figure)
        layout.addWidget(QLabel("⏰ 使用时段分布（24小时）"))
        layout.addWidget(self.hour_canvas)

        # === 最常用 Top10 ===
        layout.addWidget(QLabel("🏆 最常用 Top 10 表情"))
        self.top10_list = QListWidget()
        self.top10_list.setMaximumHeight(180)
        layout.addWidget(self.top10_list)

        # === 最近刷新时间 ===
        self.refresh_label = QLabel("")
        self.refresh_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.refresh_label)

    def _make_card(self, title: str, value: str) -> QFrame:
        """创建统计数字卡片"""
        card = QFrame()
        card.setObjectName("statsCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        card.setMinimumHeight(120)
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 16, 16, 16)
        title_lbl = AutoFitLabel(title, min_size=10, max_size=14)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("color: #aaa;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_lbl = AutoFitLabel(value, min_size=14, max_size=36)
        value_lbl.setStyleSheet("color: #4a9eff; font-weight: bold;")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title_lbl, 1)
        v.addWidget(value_lbl, 2)
        # 保存 value_lbl 引用以便更新
        card._title_label = title_lbl
        card._value_label = value_lbl
        return card

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
        ax.set_title("最近 7 天使用趋势", color='white', fontsize=11)
        ax.set_xticks(dates)
        for spine in ax.spines.values():
            spine.set_color('#3e3e42')
        self.trend_figure.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.18)
        self.trend_canvas.draw()

    def _refresh_hourly(self):
        """24小时时段分布柱状图（本地时间）"""
        self.hour_figure.clear()
        ax = self.hour_figure.add_subplot(111)
        ax.set_facecolor('#1e1e1e')
        ax.tick_params(colors='white', labelsize=8)

        hour_counts = [0] * 24
        try:
            rows = self.db.get_usage_history()
            for row in rows:
                dt = self._parse_used_at(row[2])
                if dt is not None:
                    hour_counts[dt.hour] += 1
        except Exception:
            pass

        hours = list(range(24))
        colors = ['#4a9eff' if h in range(9, 22) else '#3a6ea8' for h in hours]
        ax.bar(hours, hour_counts, color=colors, edgecolor='none')
        ax.set_title("使用时段分布", color='white', fontsize=11)
        ax.set_xticks(range(0, 24, 3))
        ax.set_xticklabels([f"{h}时" for h in range(0, 24, 3)], color='white', fontsize=8)
        for spine in ax.spines.values():
            spine.set_color('#3e3e42')
        self.hour_figure.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.18)
        self.hour_canvas.draw()

    def _refresh_top10(self):
        """最常用 Top10 表情（带缩略图）"""
        self.top10_list.clear()
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

        # 取 top10
        top10 = sorted(use_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # 延迟导入 ThumbnailService
        if self.thumb_service is None:
            from services.thumbnail_service import ThumbnailService
            self.thumb_service = ThumbnailService()

        for rank, (image_id, count) in enumerate(top10, 1):
            img_row = self.db.get_image_by_id(image_id)
            if not img_row:
                continue
            name = img_row[1]
            file_path = img_row[2]

            item = QListWidgetItem(f"#{rank}  {name}  （使用 {count} 次）")
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
