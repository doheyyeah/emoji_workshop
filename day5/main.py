import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget
from views.gallery_view import GalleryView
from views.tag_panel import TagPanel
from services.database_service import DatabaseService


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("表情工坊 - Day5 标签系统")
        self.setMinimumSize(1200, 700)
        
        self.db_service = DatabaseService()
        
        # 主布局：左侧画廊 + 右侧标签面板
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        # 左侧：画廊
        self.gallery = GalleryView(self.db_service)
        self.gallery.image_selected.connect(self.on_image_selected)
        layout.addWidget(self.gallery, 3)
        
        # 右侧：标签面板
        self.tag_panel = TagPanel(self.db_service)
        self.tag_panel.tag_selected.connect(self.on_tag_selected)
        layout.addWidget(self.tag_panel, 1)
        
        self.statusBar().showMessage("Day5: 标签系统 + 搜索筛选")
    
    def on_image_selected(self, image_id: int):
        """图片选中时，更新标签面板的当前图片"""
        self.tag_panel.set_current_image(image_id)
    
    def on_tag_selected(self, tag_ids: list):
        """标签选择变化时，筛选画廊"""
        self.gallery.filter_by_tags(tag_ids)
    
    def closeEvent(self, event):
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    app.setStyleSheet("""
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
    """)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())