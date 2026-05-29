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
    QApplication,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from controllers.recommend_controller import RecommendController
from services.database_service import DatabaseService
from services.thumbnail_service import ThumbnailService
from services.clipboard_service import ClipboardService


class RecommendPanel(QWidget):
    """智能推荐侧边栏"""

    image_selected = pyqtSignal(int)  # 选中推荐结果时发出 image_id

    def __init__(self, db_service: DatabaseService, parent=None) -> None:
        super().__init__(parent)
        self.db = db_service
        self.controller = RecommendController(db_service)
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
        self.recommend_btn = QPushButton("🔍 推荐")
        self.recommend_btn.clicked.connect(self._do_recommend)
        layout.addWidget(self.recommend_btn)

        # 关键词显示
        self.keywords_label = QLabel("识别到的关键词：—")
        self.keywords_label.setWordWrap(True)
        self.keywords_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.keywords_label)

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
            self.keywords_label.setText("识别到的关键词：（请输入上下文）")
            return

        keywords = self.controller.extract_keywords(context)
        kw_text = "、".join(keywords) if keywords else "（未提取到有效关键词）"
        self.keywords_label.setText(f"识别到的关键词：{kw_text}")

        results = self.controller.recommend(context, top_k=6)
        self._show_results(results)

    def _show_results(self, models) -> None:
        """将推荐结果渲染到列表"""
        self.result_list.clear()

        if not models:
            self.hint_label.setText("暂无推荐结果，请先导入表情包并添加标签")
            return

        self.hint_label.setText("双击结果可复制到剪贴板")

        for model in models:
            item = QListWidgetItem()
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
            if ClipboardService.is_animated(file_path):
                msg = '已复制动图到剪贴板，粘贴到微信/QQ 时请选"以图片形式发送"以保留动画'
            else:
                msg = "已复制图片到剪贴板，可粘贴到聊天框"
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
