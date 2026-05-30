import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import (
    QDialog,
    QApplication, QMainWindow, QHBoxLayout, QWidget,
    QVBoxLayout, QPushButton, QLabel, QMessageBox, QSplitter
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
from services.api_service import APIService
from utils.config_manager import ConfigManager
from utils.file_scanner import FileScanner


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

        self.setWindowTitle("表情工坊 - 智能管理系统")
        self.setMinimumSize(800, 600)

        # 恢复窗口状态
        self._restore_window_state()

        self.db_service = DatabaseService()
        self.api_service = APIService()

        self._setup_menu()
        self._setup_ui()

        self.clipboard_monitor = ClipboardMonitor()
        self.clipboard_monitor.new_image_detected.connect(self._on_new_clipboard_image)
        if self.config.get("behavior.clipboard_monitor_enabled", False):
            self.clipboard_monitor.start()

        self.statusBar().showMessage("就绪")
        self.status_tip_label = QLabel("💡 想从网页保存图片? 浏览器右键 → 图片另存为 → 然后拖入本程序")
        self.statusBar().addPermanentWidget(self.status_tip_label, 1)

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
        self.gallery.image_selected.connect(self.on_image_selected)
        self.gallery.images_selection_changed.connect(self.on_images_selection_changed)
        left_layout.addWidget(self.gallery)

        # 统计面板（默认隐藏）
        self.stats_panel = StatsPanel(self.db_service)
        self.stats_panel.setVisible(False)
        left_layout.addWidget(self.stats_panel)

        self.main_splitter.addWidget(left_container)

        # 右侧：标签面板 + 智能推荐面板（垂直 QSplitter）
        self.right_container = QWidget()
        right_layout = QVBoxLayout(self.right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.tag_panel = TagPanel(self.db_service)
        self.tag_panel.filter_tags_changed.connect(self.on_filter_tags_changed)
        self.tag_panel.tags_updated.connect(self.on_tags_updated)
        right_splitter.addWidget(self.tag_panel)

        self.recommend_panel = RecommendPanel(self.db_service)
        self.recommend_panel.image_selected.connect(self.on_image_selected)
        right_splitter.addWidget(self.recommend_panel)

        right_splitter.setSizes([300, 300])
        right_layout.addWidget(right_splitter)

        self.main_splitter.addWidget(self.right_container)
        self.main_splitter.setSizes([700, 300])

        main_layout.addWidget(self.main_splitter)

        # 应用主题
        self._apply_theme()

    def _apply_theme(self):
        """应用配置中的主题设置"""
        theme = self.config.get("ui.theme", "dark")

        if theme == "dark":
            self.setStyleSheet("""
                * {
                    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
                    font-size: 13px;
                }
                QMainWindow { background-color: #1e1e1e; }
                QWidget { background-color: #1e1e1e; color: #e0e0e0; }
                QPushButton {
                    background-color: #4a9eff;
                    color: white;
                    border: none;
                    padding: 8px 18px;
                    border-radius: 8px;
                }
                QPushButton:hover { background-color: #6ab3ff; }
                QPushButton:pressed { background-color: #3480d8; }
                QPushButton:disabled { background-color: #555; color: #888; }
                QListWidget {
                    background-color: #252526;
                    border: 1px solid #3e3e42;
                    border-radius: 8px;
                }
                QListWidget::item:hover {
                    background-color: #2e2e3a;
                }
                QListWidget::item:selected {
                    background-color: #4a9eff;
                    color: white;
                }
                QLabel { color: #e0e0e0; }
                QLineEdit, QComboBox, QTextEdit {
                    background-color: #252526;
                    color: #e0e0e0;
                    border: 1px solid #3e3e42;
                    padding: 6px;
                    border-radius: 8px;
                }
                QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                    border: 2px solid #4a9eff;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 6px;
                }
                QProgressBar {
                    border: 1px solid #3e3e42;
                    border-radius: 8px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #4a9eff;
                    border-radius: 8px;
                }
                QMenuBar {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border-bottom: 1px solid #3e3e42;
                }
                QMenuBar::item:selected {
                    background-color: #4a9eff;
                    border-radius: 4px;
                }
                QMenu {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border: 1px solid #3e3e42;
                    border-radius: 8px;
                }
                QMenu::item:selected {
                    background-color: #4a9eff;
                    border-radius: 4px;
                }
                QScrollBar:vertical {
                    background: #252526;
                    width: 8px;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical {
                    background: #555;
                    border-radius: 4px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover { background: #4a9eff; }
                QScrollBar:horizontal {
                    background: #252526;
                    height: 8px;
                    border-radius: 4px;
                }
                QScrollBar::handle:horizontal {
                    background: #555;
                    border-radius: 4px;
                    min-width: 20px;
                }
                QScrollBar::handle:horizontal:hover { background: #4a9eff; }
                QGroupBox {
                    border: 1px solid #3e3e42;
                    border-radius: 8px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    color: #4a9eff;
                    subcontrol-origin: margin;
                    left: 10px;
                }
                QTabWidget::pane {
                    border: 1px solid #3e3e42;
                    border-radius: 8px;
                }
                QTabBar::tab {
                    background: #252526;
                    color: #aaa;
                    padding: 6px 14px;
                    border-radius: 6px 6px 0 0;
                }
                QTabBar::tab:selected {
                    background: #4a9eff;
                    color: white;
                }
                QSplitter::handle { background: #3e3e42; }
            """)
        else:
            self.setStyleSheet("""
                * {
                    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
                    font-size: 13px;
                }
                QMainWindow { background-color: #f5f5f5; }
                QWidget { background-color: #f5f5f5; color: #333; }
                QPushButton {
                    background-color: #5b8def;
                    color: white;
                    border: none;
                    padding: 8px 18px;
                    border-radius: 8px;
                }
                QPushButton:hover { background-color: #3a6ed4; }
                QPushButton:pressed { background-color: #2a5ab8; }
                QPushButton:disabled { background-color: #ccc; color: #888; }
                QListWidget {
                    background-color: white;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                }
                QListWidget::item:hover { background-color: #eef2ff; }
                QListWidget::item:selected {
                    background-color: #5b8def;
                    color: white;
                }
                QLabel { color: #333; }
                QLineEdit, QComboBox, QTextEdit {
                    background-color: white;
                    color: #333;
                    border: 1px solid #ddd;
                    padding: 6px;
                    border-radius: 8px;
                }
                QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                    border: 2px solid #5b8def;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 6px;
                }
                QProgressBar {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #5b8def;
                    border-radius: 8px;
                }
                QScrollBar:vertical {
                    background: #f0f0f0;
                    width: 8px;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical {
                    background: #bbb;
                    border-radius: 4px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover { background: #5b8def; }
                QGroupBox {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    color: #5b8def;
                    subcontrol-origin: margin;
                    left: 10px;
                }
                QSplitter::handle { background: #ddd; }
            """)

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
        visible = self.right_container.isVisible()
        self.right_container.setVisible(not visible)

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
        self.api_service.cancel_all_downloads()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
