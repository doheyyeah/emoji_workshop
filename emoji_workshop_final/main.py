import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import (
    QDialog,
    QApplication, QMainWindow, QHBoxLayout, QWidget,
    QVBoxLayout, QPushButton, QMessageBox, QSplitter, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QAction

from views.gallery_view import GalleryView
from views.tag_panel import TagPanel
from views.stats_panel import StatsPanel
from views.settings_dialog import SettingsDialog
from views.ai_generate_dialog import AIGenerateDialog
from views.recommend_panel import RecommendPanel
from views.report_view import ReportDialog
from services.database_service import DatabaseService
from services.clipboard_monitor import ClipboardMonitor
from utils.config_manager import ConfigManager
from utils.file_scanner import FileScanner

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


# Some native Qt sub-controls, especially the viewport inside QListWidget/QTextEdit
# and widgets created before the mainWindow dynamic property is polished, can keep the
# dark Fusion background even when style.qss defines a light theme.  These unscoped
# runtime overrides remove the remaining dark blocks while keeping the blue-white
# palette in resources/style.qss.
HARD_LIGHT_THEME_OVERRIDES = """
/* ===== Runtime hard override: remove remaining dark native backgrounds ===== */
QWidget#galleryView,
QWidget#rightContainer,
QWidget#tagPanel,
QWidget#recommendPanel,
QScrollArea#rightScrollArea,
QScrollArea#rightScrollArea > QWidget,
QScrollArea#rightScrollArea > QWidget > QWidget {
    background-color: #f5f8fc;
    color: #223047;
}

QAbstractScrollArea,
QAbstractItemView,
QListWidget,
QListWidget#thumbList,
QListWidget#tagList,
QListWidget#imageTagList,
QListWidget#rankingList,
QTextEdit,
QTextBrowser,
QLineEdit,
QComboBox {
    background-color: #ffffff;
    color: #223047;
    border: 1px solid #c9d8ec;
    border-radius: 10px;
    selection-background-color: #d9e8ff;
    selection-color: #16345f;
}

QListWidget::viewport,
QListView::viewport,
QTextEdit::viewport,
QTextBrowser::viewport,
QAbstractScrollArea::viewport {
    background-color: #ffffff;
    color: #223047;
}

QListWidget#thumbList,
QListWidget#thumbList::viewport,
QListWidget#tagList,
QListWidget#tagList::viewport,
QListWidget#imageTagList,
QListWidget#imageTagList::viewport,
QListWidget#rankingList,
QListWidget#rankingList::viewport {
    background-color: #ffffff;
    color: #223047;
}

QWidget#tagPanel QWidget,
QWidget#recommendPanel QWidget {
    background-color: #f5f8fc;
    color: #223047;
}

QWidget#tagPanel QLineEdit,
QWidget#tagPanel QListWidget,
QWidget#tagPanel QListWidget::viewport,
QWidget#recommendPanel QTextEdit,
QWidget#recommendPanel QTextEdit::viewport,
QWidget#recommendPanel QListWidget,
QWidget#recommendPanel QListWidget::viewport {
    background-color: #ffffff;
    color: #223047;
    border: 1px solid #c9d8ec;
}

QListWidget::item {
    background-color: transparent;
    color: #223047;
    border-radius: 8px;
    padding: 4px;
}

QListWidget::item:hover {
    background-color: #edf4ff;
}

QListWidget::item:selected {
    background-color: #d9e8ff;
    color: #16345f;
}

QSplitter::handle {
    background-color: #dbe6f5;
}

QSplitter::handle:hover {
    background-color: #b9ccea;
}

QScrollBar:vertical {
    background: #e7eef8;
    width: 10px;
    margin: 2px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #aebfda;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #8fa7cc;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: #e7eef8;
    border-radius: 5px;
}

QScrollBar:horizontal {
    background: #e7eef8;
    height: 10px;
    margin: 2px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #aebfda;
    border-radius: 5px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: #8fa7cc;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: #e7eef8;
    border-radius: 5px;
}

QScrollBar::add-line,
QScrollBar::sub-line {
    width: 0;
    height: 0;
}
"""


class MainWindow(QMainWindow):
    """表情工坊主窗口 - Day7 AI 生成版

    Day7 新增：
    - AI 文生图功能（Pollinations.ai 免费 / 硅基流动）
    - 快捷提示词模板
    - 生成后一键导入图片库
    """

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.config.increment_stat("launch_count")
        self.setObjectName("mainWindow")

        self.setWindowTitle("表情工坊 - 智能管理系统")
        self.setMinimumSize(800, 600)

        # 恢复窗口状态
        self._restore_window_state()

        self.db_service = DatabaseService()

        self._setup_menu()
        self._setup_ui()

        self.clipboard_monitor = ClipboardMonitor()
        self.clipboard_monitor.new_image_detected.connect(self._on_new_clipboard_image)
        if self.config.get("behavior.clipboard_monitor_enabled", False):
            self.clipboard_monitor.start()

        self.statusBar().showMessage("就绪")

    def _restore_window_state(self):
        """从配置恢复窗口位置和大小"""
        width = self.config.get("window.width", 1000)
        height = self.config.get("window.height", 650)
        pos_x = self.config.get("window.pos_x", 100)
        pos_y = self.config.get("window.pos_y", 100)
        maximized = self.config.get("window.maximized", False)

        self.setGeometry(pos_x, pos_y, width, height)
        if maximized:
            self.showMaximized()

    def _setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        # AI 生成（Day7 新增）
        ai_action = QAction("🎨 AI 生成表情包", self)
        ai_action.setShortcut("Ctrl+G")
        ai_action.triggered.connect(self._open_ai_dialog)
        file_menu.addAction(ai_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图")

        stats_action = QAction("📊 数据统计", self)
        stats_action.setShortcut("Ctrl+T")
        stats_action.triggered.connect(self._toggle_stats_panel)
        view_menu.addAction(stats_action)

        report_action = QAction("📝 性格画像报告", self)
        report_action.setShortcut("Ctrl+R")
        report_action.triggered.connect(self._open_report_dialog)
        view_menu.addAction(report_action)

        view_menu.addSeparator()

        toggle_panel_action = QAction("隐藏/显示右侧面板", self)
        toggle_panel_action.setShortcut("F9")
        toggle_panel_action.triggered.connect(self._toggle_right_panel)
        view_menu.addAction(toggle_panel_action)

        # 设置菜单
        settings_action = QAction("⚙️ 设置", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        menubar.addAction(settings_action)

    def _setup_ui(self):
        """设置主界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 主分割器（左右可拖拽调整）
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧主区域
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 画廊视图
        self.gallery = GalleryView(self.db_service)
        self.gallery.setObjectName("galleryView")
        self.gallery.image_selected.connect(self.on_image_selected)
        self.gallery.images_selection_changed.connect(self.on_images_selection_changed)
        left_layout.addWidget(self.gallery)

        # 统计面板（默认隐藏）
        self.stats_panel = StatsPanel(self.db_service)
        self.stats_panel.setVisible(False)
        left_layout.addWidget(self.stats_panel)

        self.main_splitter.addWidget(left_container)

        # 右侧：标签面板 + 智能推荐面板（固定纵向布局，外层支持滚轮查看）
        self.right_container = QWidget()
        self.right_container.setObjectName("rightContainer")
        right_layout = QVBoxLayout(self.right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.tag_panel = TagPanel(self.db_service)
        self.tag_panel.setObjectName("tagPanel")
        self.tag_panel.filter_tags_changed.connect(self.on_filter_tags_changed)
        self.tag_panel.tags_updated.connect(self.on_tags_updated)
        right_layout.addWidget(self.tag_panel)

        self.recommend_panel = RecommendPanel(self.db_service)
        self.recommend_panel.setObjectName("recommendPanel")
        self.recommend_panel.image_selected.connect(self.on_image_selected)
        right_layout.addWidget(self.recommend_panel)
        right_layout.addStretch(1)

        self.right_scroll_area = QScrollArea()
        self.right_scroll_area.setObjectName("rightScrollArea")
        self.right_scroll_area.setWidgetResizable(True)
        self.right_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.right_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_scroll_area.setWidget(self.right_container)

        self.main_splitter.addWidget(self.right_scroll_area)
        self.main_splitter.setSizes([700, 300])

        main_layout.addWidget(self.main_splitter)

        # 应用主题
        self._apply_theme()

    def _apply_theme(self):
        """固定使用 dark 主题，并强制刷新所有子控件样式。"""
        self.setProperty("theme", "dark")
        # Apply unscoped overrides on the main window so child viewports also inherit
        # the light blue-white palette instead of the native dark Fusion background.
        self.setStyleSheet(HARD_LIGHT_THEME_OVERRIDES)

        widgets = [self] + self.findChildren(QWidget)
        for widget in widgets:
            widget.setProperty("theme", "dark")
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        app = QApplication.instance()
        if app:
            app.style().unpolish(app)
            app.style().polish(app)

    def _open_report_dialog(self):
        """打开性格画像报告对话框"""
        dialog = ReportDialog(self.db_service, self)
        dialog.exec()

    def _open_ai_dialog(self):
        """打开 AI 生成对话框（Day7 新增）"""
        dialog = AIGenerateDialog(self.db_service, self)
        dialog.exec()
        # AI 生成后刷新画廊
        self.gallery.load_from_database()

    def _open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_theme()
            new_size = self.config.get("ui.thumbnail_size", 128)
            self.gallery.THUMBNAIL_SIZE = new_size
            self.gallery.list_widget.setIconSize(QSize(new_size, new_size))
            self.gallery.load_from_database()
            if self.config.get("behavior.clipboard_monitor_enabled", False):
                self.clipboard_monitor.start()
            else:
                self.clipboard_monitor.stop()

    def _toggle_right_panel(self):
        """切换右侧面板显示/隐藏（F9）"""
        visible = self.right_scroll_area.isVisible()
        self.right_scroll_area.setVisible(not visible)

    def _toggle_stats_panel(self):
        """切换统计面板显示/隐藏"""
        is_visible = self.stats_panel.isVisible()
        self.stats_panel.setVisible(not is_visible)
        self.gallery.setVisible(is_visible)

        if not is_visible:
            self.stats_panel.refresh_stats()

    def on_image_selected(self, image_id: int):
        """图片选中时更新标签面板（向后兼容单图）"""
        self.tag_panel.set_current_image(image_id)

    def on_images_selection_changed(self, image_ids: list):
        """多图选中时批量更新标签面板"""
        self.tag_panel.set_current_images(image_ids)

    def on_filter_tags_changed(self, tag_names: list, match_mode: str):
        """标签选择变化时筛选画廊"""
        self.gallery.filter_by_tag_names(tag_names, match_mode)

    def on_tags_updated(self):
        """标签更新后刷新当前画廊"""
        self.gallery.load_from_database()

    def _on_new_clipboard_image(self, image):
        reply = QMessageBox.question(
            self,
            "检测到剪贴板图片",
            "检测到新图片，是否加入库？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        save_dir = Path(self.config.get("paths.last_import_folder", str(Path.home() / "Pictures")))
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"clipboard_{int(time.time())}.png"
        image.save(str(save_path))
        info = FileScanner.get_image_info(str(save_path))
        if info:
            self.db_service.add_image(**info)
            self.gallery.load_from_database()
            self.statusBar().showMessage("已从剪贴板加入图片到库", 2000)

    def closeEvent(self, event):
        """关闭时保存窗口状态"""
        if self.isMaximized():
            self.config.set("window.maximized", True)
        else:
            self.config.set("window.maximized", False)
            self.config.set("window.width", self.width())
            self.config.set("window.height", self.height())
            self.config.set("window.pos_x", self.x())
            self.config.set("window.pos_y", self.y())

        self.config.save()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    qss_path = Path(__file__).parent / "resources" / "style.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
