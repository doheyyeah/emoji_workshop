import sys
from pathlib import Path

# 确保能导入同级目录的模块
sys.path.insert(0, str(Path(__file__).parent))

from views.gallery_view import MainWindow
from PyQt6.QtWidgets import QApplication


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 深色主题样式
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