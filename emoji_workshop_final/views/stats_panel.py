import sys
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

# Matplotlib 嵌入 PyQt6
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.database_service import DatabaseService
from utils.config_manager import ConfigManager


class StatsPanel(QWidget):
    """数据统计面板：图表 + 表格展示

    功能：
    - 图片格式分布饼图
    - 文件大小分布柱状图
    - 标签使用频率统计
    - 月度导入趋势（模拟）
    """

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.config = ConfigManager()
        self.setup_ui()
        self.refresh_stats()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # === 顶部工具栏 ===
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("📊 数据统计"))
        toolbar.addStretch()

        self.chart_combo = QComboBox()
        self.chart_combo.addItems([
            "格式分布", "大小分布", "标签统计", "导入趋势"
        ])
        self.chart_combo.currentIndexChanged.connect(self.refresh_stats)
        toolbar.addWidget(QLabel("图表类型:"))
        toolbar.addWidget(self.chart_combo)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.refresh_stats)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        # === 图表区域 ===
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.figure.patch.set_facecolor('#1e1e1e')
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # === 数据表格 ===
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["项目", "数值", "占比"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(200)
        layout.addWidget(self.table)

        # === 底部统计 ===
        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

    def refresh_stats(self):
        """刷新所有统计数据"""
        chart_type = self.chart_combo.currentText()

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('#1e1e1e')
        ax.tick_params(colors='white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')

        if chart_type == "格式分布":
            self._draw_format_chart(ax)
        elif chart_type == "大小分布":
            self._draw_size_chart(ax)
        elif chart_type == "标签统计":
            self._draw_tag_chart(ax)
        elif chart_type == "导入趋势":
            self._draw_trend_chart(ax)

        self.canvas.draw()

    def _draw_format_chart(self, ax):
        """图片格式分布饼图"""
        rows = self.db.get_all_images()
        if not rows:
            ax.text(0.5, 0.5, "暂无数据", ha='center', va='center', 
                   transform=ax.transAxes, color='white', fontsize=14)
            self.table.setRowCount(0)
            self.summary_label.setText("暂无图片数据")
            return

        # 统计格式
        format_counts = {}
        total_size = 0
        for row in rows:
            fmt = row[3].upper()  # file_type
            size = row[4]         # file_size
            format_counts[fmt] = format_counts.get(fmt, 0) + 1
            total_size += size

        labels = list(format_counts.keys())
        sizes = list(format_counts.values())
        colors = plt.cm.Set3(range(len(labels)))

        ax.pie(sizes, labels=labels, autopct='%1.1f%%', 
               colors=colors, textprops={'color': 'white'})
        ax.set_title("图片格式分布", color='white', fontsize=14)

        # 更新表格
        self.table.setRowCount(len(labels))
        for i, (fmt, count) in enumerate(sorted(format_counts.items(), 
                                                 key=lambda x: -x[1])):
            self.table.setItem(i, 0, QTableWidgetItem(fmt))
            self.table.setItem(i, 1, QTableWidgetItem(str(count)))
            pct = count / len(rows) * 100
            self.table.setItem(i, 2, QTableWidgetItem(f"{pct:.1f}%"))

        size_mb = total_size / (1024 * 1024)
        self.summary_label.setText(
            f"总计 {len(rows)} 张图片 | 总大小 {size_mb:.2f} MB | "
            f"平均 {size_mb/len(rows):.2f} MB/张"
        )

    def _draw_size_chart(self, ax):
        """文件大小分布柱状图"""
        rows = self.db.get_all_images()
        if not rows:
            ax.text(0.5, 0.5, "暂无数据", ha='center', va='center',
                   transform=ax.transAxes, color='white', fontsize=14)
            self.table.setRowCount(0)
            return

        # 分桶统计（MB）
        buckets = {"< 0.1MB": 0, "0.1-0.5MB": 0, "0.5-1MB": 0, 
                   "1-2MB": 0, "2-5MB": 0, "> 5MB": 0}
        for row in rows:
            size_mb = row[4] / (1024 * 1024)
            if size_mb < 0.1:
                buckets["< 0.1MB"] += 1
            elif size_mb < 0.5:
                buckets["0.1-0.5MB"] += 1
            elif size_mb < 1:
                buckets["0.5-1MB"] += 1
            elif size_mb < 2:
                buckets["1-2MB"] += 1
            elif size_mb < 5:
                buckets["2-5MB"] += 1
            else:
                buckets["> 5MB"] += 1

        labels = list(buckets.keys())
        values = list(buckets.values())
        colors = ['#0d7377' if v > 0 else '#555' for v in values]

        bars = ax.bar(labels, values, color=colors, edgecolor='white')
        ax.set_title("文件大小分布", color='white', fontsize=14)
        ax.set_ylabel("图片数量", color='white')

        # 在柱子上显示数值
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                       str(val), ha='center', va='bottom', color='white')

        # 更新表格
        self.table.setRowCount(len(labels))
        total = sum(values)
        for i, (label, count) in enumerate(buckets.items()):
            self.table.setItem(i, 0, QTableWidgetItem(label))
            self.table.setItem(i, 1, QTableWidgetItem(str(count)))
            pct = count / total * 100 if total > 0 else 0
            self.table.setItem(i, 2, QTableWidgetItem(f"{pct:.1f}%"))

        self.summary_label.setText(f"总计 {total} 张图片")

    def _draw_tag_chart(self, ax):
        """标签使用频率横向柱状图"""
        # 获取所有标签及使用次数
        tags = self.db.get_all_tags()
        if not tags:
            ax.text(0.5, 0.5, "暂无标签", ha='center', va='center',
                   transform=ax.transAxes, color='white', fontsize=14)
            self.table.setRowCount(0)
            return

        # 统计每个标签关联的图片数
        tag_counts = []
        for tag_id, name, color in tags:
            # 通过数据库查询该标签关联的图片数
            count = self._count_images_by_tag(tag_id)
            tag_counts.append((name, count, color))

        tag_counts.sort(key=lambda x: x[1], reverse=True)
        names = [t[0] for t in tag_counts]
        counts = [t[1] for t in tag_counts]
        colors = [t[2] for t in tag_counts]

        y_pos = range(len(names))
        ax.barh(y_pos, counts, color=colors, edgecolor='white')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, color='white')
        ax.invert_yaxis()
        ax.set_title("标签使用频率", color='white', fontsize=14)
        ax.set_xlabel("关联图片数", color='white')

        # 更新表格
        self.table.setRowCount(len(names))
        total = sum(counts)
        for i, (name, count, _) in enumerate(tag_counts):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem(str(count)))
            pct = count / total * 100 if total > 0 else 0
            self.table.setItem(i, 2, QTableWidgetItem(f"{pct:.1f}%"))

        self.summary_label.setText(f"共 {len(names)} 个标签 | 总计使用 {total} 次")

    def _draw_trend_chart(self, ax):
        """导入趋势折线图（按创建时间）"""
        rows = self.db.get_all_images()
        if not rows:
            ax.text(0.5, 0.5, "暂无数据", ha='center', va='center',
                   transform=ax.transAxes, color='white', fontsize=14)
            self.table.setRowCount(0)
            return

        # 按日期分组（使用 created_at）
        from collections import defaultdict
        from datetime import datetime

        daily_counts = defaultdict(int)
        for row in rows:
            # row[8] 是 created_at，格式如 "2026-05-15 13:42:00"
            try:
                if len(row) > 8 and row[8]:
                    date_str = str(row[8])[:10]  # 取 YYYY-MM-DD
                    daily_counts[date_str] += 1
                else:
                    daily_counts["未知日期"] += 1
            except Exception as e:
                print(f"[StatsPanel] 日期解析错误: {e}, row={row}")
                daily_counts["未知日期"] += 1

        dates = sorted(daily_counts.keys())
        counts = [daily_counts[d] for d in dates]

        ax.plot(dates, counts, marker='o', color='#0d7377', 
                linewidth=2, markersize=6)
        ax.fill_between(dates, counts, alpha=0.3, color='#0d7377')
        ax.set_title("每日导入趋势", color='white', fontsize=14)
        ax.set_ylabel("导入数量", color='white')
        ax.tick_params(axis='x', rotation=45)

        # 更新表格
        self.table.setRowCount(len(dates))
        total = sum(counts)
        for i, date in enumerate(dates):
            self.table.setItem(i, 0, QTableWidgetItem(date))
            self.table.setItem(i, 1, QTableWidgetItem(str(daily_counts[date])))
            pct = daily_counts[date] / total * 100 if total > 0 else 0
            self.table.setItem(i, 2, QTableWidgetItem(f"{pct:.1f}%"))

        self.summary_label.setText(f"共 {len(dates)} 天有导入记录 | 总计 {total} 张")

    def _count_images_by_tag(self, tag_id: int) -> int:
        """统计标签关联的图片数"""
        # 复用 search_images_by_tags 逻辑
        rows = self.db.search_images_by_tags([tag_id])
        return len(rows)
