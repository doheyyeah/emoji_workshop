"""智能推荐面板

功能：
- 输入聊天上下文，提取关键词，推荐相关表情包
- 点击推荐结果双击复制到剪贴板
- 适配 dark 主题
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from controllers.recommend_controller import RecommendController
from services.database_service import DatabaseService
from services.thumbnail_service import ThumbnailService
from services.clipboard_service import ClipboardService
from utils.config_manager import ConfigManager


class RecommendPanel(QWidget):
    """智能推荐侧边栏"""

    image_selected = pyqtSignal(int)  # 选中推荐结果时发出 image_id

    def __init__(self, db_service: DatabaseService, parent=None) -> None:
        super().__init__(parent)
        self.db = db_service
        self.controller = RecommendController(db_service)
        self.config = ConfigManager()
        self.thumb_service = ThumbnailService()
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 标题
        title = QLabel("🎯 智能推荐")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px 0;")
        layout.addWidget(title)

        # 输入框
        self.context_input = QTextEdit()
        self.context_input.setPlaceholderText("粘贴聊天上下文...")
        self.context_input.setFixedHeight(80)
        layout.addWidget(self.context_input)

        # 推荐按钮
        btn_row = QHBoxLayout()
        self.recommend_btn = QPushButton("🔍 推荐")
        self.recommend_btn.clicked.connect(self._do_recommend)
        self.goto_settings_btn = QPushButton("前往设置")
        self.goto_settings_btn.clicked.connect(self._goto_settings)
        self.goto_settings_btn.setVisible(False)
        btn_row.addWidget(self.recommend_btn)
        btn_row.addWidget(self.goto_settings_btn)
        layout.addLayout(btn_row)

        self.error_label = QLabel("⚠️ 请先在 设置 → AI 推荐 中配置 LLM API Key")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        self.error_label.setVisible(not self.config.is_llm_enabled())
        layout.addWidget(self.error_label)

        # 推荐结果列表
        self.result_list = QListWidget()
        self.result_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.result_list.setIconSize(QSize(96, 96))
        self.result_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.result_list.setSpacing(6)
        self.result_list.setMinimumHeight(200)
        self.result_list.itemDoubleClicked.connect(self._on_double_click)
        self.result_list.itemClicked.connect(self._on_single_click)
        layout.addWidget(self.result_list)

        # 提示文字
        self.hint_label = QLabel("双击结果可复制到剪贴板")
        self.hint_label.setStyleSheet("color: #666; font-size: 10px;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

    # ------------------------------------------------------------------
    # 槽函数
    # ------------------------------------------------------------------

    def _do_recommend(self) -> None:
        """执行推荐逻辑"""
        context = self.context_input.toPlainText().strip()
        if not context:
            self.error_label.setText("请输入聊天上下文后再推荐")
            return

        try:
            results = self.controller.recommend(context, top_k=6)
            tags = self.controller.last_recommended_tags
            self.error_label.setText("")
            self.error_label.setVisible(False)
            self.goto_settings_btn.setVisible(False)
            self._show_results(results)
        except Exception as exc:
            self.result_list.clear()
            self.hint_label.setText("推荐失败")
            self.error_label.setText(str(exc))
            self.error_label.setVisible(True)
            self.goto_settings_btn.setVisible(True)

    def _show_results(self, models) -> None:
        """将推荐结果渲染到列表，第 1 项添加 ⭐ 最佳推荐角标"""
        self.result_list.clear()

        if not models:
            self.hint_label.setText("暂无推荐结果，请先导入表情包并添加标签")
            return

        self.hint_label.setText("双击结果可复制到剪贴板")

        for idx, model in enumerate(models):
            item = QListWidgetItem()
            # 第 1 个结果加 ⭐ 角标
            if idx == 0:
                item.setText(f"⭐ 最佳推荐 | {model.display_name}")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item.setText(model.display_name)
            item.setData(Qt.ItemDataRole.UserRole, model.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, model.file_path)

            # 加载缩略图
            thumb_path = model.thumbnail_path
            if not thumb_path or not Path(thumb_path).exists():
                thumb_path = self.thumb_service.get_thumbnail(model.file_path)

            pixmap = QPixmap(thumb_path) if thumb_path else QPixmap(model.file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    96, 96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item.setIcon(QIcon(scaled))

            self.result_list.addItem(item)

    def _on_single_click(self, item: QListWidgetItem) -> None:
        """单击发射 image_selected 信号"""
        image_id = item.data(Qt.ItemDataRole.UserRole)
        if image_id is not None:
            self.image_selected.emit(image_id)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        """双击：复制图片到剪贴板并提示"""
        file_path = item.data(Qt.ItemDataRole.UserRole + 1)
        if not file_path or not Path(file_path).exists():
            return

        if ClipboardService.copy_image(file_path):
            image_id = item.data(Qt.ItemDataRole.UserRole)
            if image_id:
                self.db.record_usage(image_id)
            msg = "已复制 + 已记录使用"
            self.hint_label.setText(f"✅ {msg}")
            # 通知主窗口状态栏
            main_win = self.window()
            if hasattr(main_win, 'statusBar'):
                main_win.statusBar().showMessage(msg, 2000)
        else:
            self.hint_label.setText("❌ 复制失败")
        # 3 秒后恢复提示文字
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self.hint_label.setText("双击结果可复制到剪贴板"))

    def _goto_settings(self):
        main_win = self.window()
        if hasattr(main_win, "_open_settings"):
            main_win._open_settings()
