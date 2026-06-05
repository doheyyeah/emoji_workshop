"""性格画像报告对话框

功能：
- 粒度选择（本周 / 本月 / 全部）
- 富文本 HTML 报告展示
- 保存为 PNG 截图
- 适配 dark 主题
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
)

from controllers.report_controller import ReportController
from services.database_service import DatabaseService


class ReportDialog(QDialog):
    """性格画像报告对话框"""

    def __init__(self, db_service: DatabaseService, parent=None) -> None:
        super().__init__(parent)
        self.db = db_service
        self.controller = ReportController(db_service)
        self.setObjectName("reportDialog")

        self.setWindowTitle("📝 性格画像报告")
        self.setMinimumSize(600, 500)
        self.resize(700, 580)

        self._setup_ui()
        self._apply_dark_style()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- 统计规则说明 ---
        stats_rule_label = QLabel(
            "📊 统计规则：每次双击图片（自动复制到剪贴板）记为 1 次使用"
        )
        stats_rule_label.setObjectName("statsRuleLabel")
        layout.addWidget(stats_rule_label)

        # --- 顶部工具栏 ---
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("统计粒度："))

        self.period_combo = QComboBox()
        self.period_combo.addItems(["本周", "本月", "全部"])
        toolbar.addWidget(self.period_combo)

        self.generate_btn = QPushButton("📊 生成报告")
        self.generate_btn.setObjectName("primaryButton")
        self.generate_btn.clicked.connect(self._generate)
        toolbar.addWidget(self.generate_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # --- 报告展示区 ---
        self.browser = QTextBrowser()
        self.browser.setObjectName("reportBrowser")
        self.browser.setOpenExternalLinks(False)
        self.browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.browser.setHtml(
            "<p style='color:#888; text-align:center; margin-top:40px;'>"
            "点击「生成报告」查看你的性格画像 ✨</p>"
        )
        layout.addWidget(self.browser)

        # --- 底部按钮 ---
        btn_row = QHBoxLayout()

        self.save_btn = QPushButton("💾 保存为图片")
        self.save_btn.setObjectName("secondaryButton")
        self.save_btn.clicked.connect(self._save_as_image)
        btn_row.addWidget(self.save_btn)

        btn_row.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # 槽函数
    # ------------------------------------------------------------------

    def _generate(self) -> None:
        """生成并显示报告"""
        period_map = {"本周": "week", "本月": "month", "全部": "all"}
        period_key = period_map.get(self.period_combo.currentText(), "week")

        try:
            report = self.controller.generate_report(period_key)
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"生成报告失败：{exc}")
            return

        self.browser.setHtml(report.get("summary_text", "<p>暂无数据</p>"))

    def _save_as_image(self) -> None:
        """将 QTextBrowser 内容截图并保存为 PNG"""
        path, _ = QFileDialog.getSaveFileName(
            self, "保存报告图片", "report.png", "PNG 图片 (*.png)"
        )
        if not path:
            return

        pixmap = self.browser.grab()
        if pixmap.save(path, "PNG"):
            QMessageBox.information(self, "完成", f"报告已保存至：{path}")
        else:
            QMessageBox.warning(self, "失败", "保存图片失败，请检查路径权限")

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def _apply_dark_style(self) -> None:
        """样式由全局 QSS 控制"""
