import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QFileDialog,
    QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon


class ImageBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("表情工坊 - Day2 图片浏览器")
        self.setGeometry(100, 100, 900, 600)
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        # ===== 左侧：图片列表 =====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 导入按钮
        self.btn_import = QPushButton("📁 导入文件夹")
        self.btn_import.setStyleSheet("font-size: 14px; padding: 8px;")
        self.btn_import.clicked.connect(self.import_folder)
        left_layout.addWidget(self.btn_import)
        
        # 清空按钮
        self.btn_clear = QPushButton("🗑️ 清空列表")
        self.btn_clear.setStyleSheet("font-size: 14px; padding: 8px;")
        self.btn_clear.clicked.connect(self.clear_list)
        left_layout.addWidget(self.btn_clear)
        
        # 图片列表
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(100, 100))
        self.list_widget.setSpacing(10)
        
        # 设置为图标模式（更像图片墙）
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        # 设置每个项的固定大小（包含文字）
        self.list_widget.setGridSize(QSize(120, 140))
        
        self.list_widget.itemClicked.connect(self.show_image)
        left_layout.addWidget(self.list_widget)
        
        # 状态标签
        self.status_label = QLabel("未导入图片")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.status_label)
        
        main_layout.addWidget(left_panel, 1)
        
        # ===== 右侧：大图预览 =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.image_label = QLabel("请选择图片")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px dashed #cccccc;
                border-radius: 10px;
                font-size: 18px;
                color: #666666;
            }
        """)
        self.image_label.setMinimumSize(400, 400)
        right_layout.addWidget(self.image_label)
        
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-size: 12px; color: #666;")
        right_layout.addWidget(self.info_label)
        
        main_layout.addWidget(right_panel, 2)
        
        self.image_paths = []
    
    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if not folder:
            return
        
        extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        files = [f for f in os.listdir(folder) 
                 if f.lower().endswith(extensions)]
        files.sort()
        
        if not files:
            QMessageBox.information(self, "提示", "该文件夹没有图片")
            return
        
        self.list_widget.clear()
        self.image_paths.clear()
        
        for filename in files:
            path = os.path.join(folder, filename)
            self.image_paths.append(path)
            
            item = QListWidgetItem(filename)
            
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(100, 100, 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                item.setIcon(QIcon(scaled))
            
            self.list_widget.addItem(item)
        
        self.status_label.setText(f"共 {len(files)} 张图片")
    
    def show_image(self, item: QListWidgetItem):
        index = self.list_widget.row(item)
        path = self.image_paths[index]
        
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_label.setText("无法加载图片")
            return
        
        label_size = self.image_label.size()
        scaled = pixmap.scaled(label_size.width() - 20, 
                               label_size.height() - 20,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        
        self.image_label.setPixmap(scaled)
        
        size_kb = os.path.getsize(path) / 1024
        self.info_label.setText(
            f"文件名：{item.text()}\n"
            f"尺寸：{pixmap.width()} x {pixmap.height()}\n"
            f"大小：{size_kb:.1f} KB"
        )
    
    # 清空方法
    def clear_list(self):
        self.list_widget.clear()
        self.image_paths.clear()
        self.image_label.setText("请选择图片")
        self.image_label.setPixmap(QPixmap())  # 清空图片显示
        self.info_label.setText("")
        self.status_label.setText("未导入图片")


def main():
    app = QApplication(sys.argv)
    window = ImageBrowser()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()