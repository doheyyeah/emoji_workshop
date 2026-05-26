import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import (
    QDialog,
    QApplication, QMainWindow, QHBoxLayout, QWidget, 
    QVBoxLayout, QPushButton, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QAction

from views.gallery_view import GalleryView
from views.tag_panel import TagPanel
from views.stats_panel import StatsPanel
from views.settings_dialog import SettingsDialog
from views.download_dialog import DownloadDialog
from views.ai_generate_dialog import AIGenerateDialog
from services.database_service import DatabaseService
from services.api_service import APIService
from utils.config_manager import ConfigManager


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

        self.setWindowTitle("表情工坊 - Day7 AI 生成")
        self.setMinimumSize(800, 600)

        # 恢复窗口状态
        self._restore_window_state()

        self.db_service = DatabaseService()
        self.api_service = APIService()

        self._setup_menu()
        self._setup_ui()

        self.statusBar().showMessage("Day7: AI 文生图 + 配置持久化 + 网络下载 + 数据统计")

    def _restore_window_state(self):
        """从配置恢复窗口位置和大小"""
        width = self.config.get("window.width", 1200)
        height = self.config.get("window.height", 700)
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

        download_action = QAction("🌐 下载网络图片", self)
        download_action.setShortcut("Ctrl+D")
        download_action.triggered.connect(self._open_download_dialog)
        file_menu.addAction(download_action)

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

        # 左侧主区域
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 画廊视图
        self.gallery = GalleryView(self.db_service)
        self.gallery.image_selected.connect(self.on_image_selected)
        left_layout.addWidget(self.gallery)

        # 统计面板（默认隐藏）
        self.stats_panel = StatsPanel(self.db_service)
        self.stats_panel.setVisible(False)
        left_layout.addWidget(self.stats_panel)

        main_layout.addWidget(left_container, 3)

        # 右侧：标签面板
        self.tag_panel = TagPanel(self.db_service)
        self.tag_panel.tag_selected.connect(self.on_tag_selected)
        main_layout.addWidget(self.tag_panel, 1)

        # 应用主题
        self._apply_theme()

    def _apply_theme(self):
        """应用配置中的主题设置"""
        theme = self.config.get("ui.theme", "dark")

        if theme == "dark":
            self.setStyleSheet("""
                QMainWindow { background-color: #1e1e1e; }
                QWidget { background-color: #1e1e1e; color: #e0e0e0; }
                QPushButton {
                    background-color: #0d7377;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #14919b; }
                QPushButton:disabled { background-color: #555; }
                QListWidget {
                    background-color: #252526;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                }
                QLabel { color: #e0e0e0; }
                QLineEdit {
                    background-color: #252526;
                    color: #e0e0e0;
                    border: 1px solid #3e3e42;
                    padding: 6px;
                    border-radius: 4px;
                }
                QProgressBar {
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #0d7377;
                }
                QMenuBar {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                }
                QMenuBar::item:selected {
                    background-color: #0d7377;
                }
                QMenu {
                    background-color: #2d2d2d;
                    color: #e0e0e0;
                    border: 1px solid #3e3e42;
                }
                QMenu::item:selected {
                    background-color: #0d7377;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: #f5f5f5; }
                QWidget { background-color: #f5f5f5; color: #333; }
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #1976D2; }
                QPushButton:disabled { background-color: #ccc; }
                QListWidget {
                    background-color: white;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
                QLabel { color: #333; }
                QLineEdit {
                    background-color: white;
                    color: #333;
                    border: 1px solid #ddd;
                    padding: 6px;
                    border-radius: 4px;
                }
                QProgressBar {
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #2196F3;
                }
            """)

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

    def _open_download_dialog(self):
        """打开网络下载对话框"""
        dialog = DownloadDialog(self.db_service, self)
        dialog.exec()
        self.gallery.load_from_database()

    def _toggle_stats_panel(self):
        """切换统计面板显示/隐藏"""
        is_visible = self.stats_panel.isVisible()
        self.stats_panel.setVisible(not is_visible)
        self.gallery.setVisible(is_visible)

        if not is_visible:
            self.stats_panel.refresh_stats()

    def on_image_selected(self, image_id: int):
        """图片选中时更新标签面板"""
        self.tag_panel.set_current_image(image_id)

    def on_tag_selected(self, tag_ids: list):
        """标签选择变化时筛选画廊"""
        self.gallery.filter_by_tags(tag_ids)

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
