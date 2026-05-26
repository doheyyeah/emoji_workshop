import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QFileDialog,
    QMessageBox, QSplitter, QStatusBar
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon

# 导入我们的模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from services.database_service import DatabaseService
from models.image_model import ImageModel
from utils.file_scanner import FileScanner


class GalleryView(QWidget):
    """图片画廊视图：从数据库加载，支持文件夹导入"""
    
    THUMBNAIL_SIZE = 120
    
    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.current_images: list[ImageModel] = []
        self.setup_ui()
        self.load_from_database()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # === 顶部工具栏 ===
        toolbar = QHBoxLayout()
        
        self.import_btn = QPushButton("📁 导入文件夹")
        self.import_btn.setMinimumHeight(32)
        self.import_btn.clicked.connect(self.import_folder)
        
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.clicked.connect(self.clear_all)
        
        self.stats_label = QLabel("图片: 0 | 总大小: 0 MB")
        
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.stats_label)
        
        layout.addLayout(toolbar)
        
        # === 主区域：列表 + 预览 ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：缩略图列表
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setSpacing(10)
        self.list_widget.setMinimumWidth(400)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        
        # 右侧：大图预览
        self.preview_label = QLabel("点击左侧图片预览\n或导入文件夹开始")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 400)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                color: #888;
                border: 2px dashed #555;
                border-radius: 8px;
            }
        """)
        
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.preview_label)
        splitter.setSizes([500, 500])
        
        layout.addWidget(splitter)
        
        # === 底部信息栏 ===
        self.info_label = QLabel("就绪")
        layout.addWidget(self.info_label)
    
    def import_folder(self):
        """导入文件夹中的图片到数据库"""
        folder = QFileDialog.getExistingDirectory(self, "选择表情包文件夹")
        if not folder:
            return
        
        self.info_label.setText("正在扫描文件夹...")
        QApplication.processEvents()  # 刷新UI
        
        # 扫描图片
        images_info = FileScanner.scan_folder(folder)
        
        if not images_info:
            QMessageBox.information(self, "提示", "未找到支持的图片文件")
            return
        
        # 批量入库
        added_count = 0
        for info in images_info:
            image_id = self.db.add_image(**info)
            if image_id:
                added_count += 1
        
        self.info_label.setText(f"成功导入 {added_count} 张图片")
        self.load_from_database()  # 刷新显示
        self.update_stats()
    
    def load_from_database(self):
        """从数据库加载所有图片显示"""
        self.list_widget.clear()
        self.current_images = []
        
        rows = self.db.get_all_images()
        for row in rows:
            model = ImageModel.from_db_row(row)
            self.current_images.append(model)
            self._add_thumbnail(model)
        
        self.update_stats()
    
    def _add_thumbnail(self, model: ImageModel):
        """添加缩略图到列表"""
        item = QListWidgetItem()
        item.setText(model.display_name)
        item.setData(Qt.ItemDataRole.UserRole, model.id)  # 存储ID
        
        # 加载缩略图
        pixmap = QPixmap(model.file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            item.setIcon(QIcon(scaled))
        
        self.list_widget.addItem(item)
    
    def on_item_clicked(self, item: QListWidgetItem):
        """点击缩略图显示大图"""
        image_id = item.data(Qt.ItemDataRole.UserRole)
        model = next((m for m in self.current_images if m.id == image_id), None)
        
        if not model:
            return
        
        # 显示大图
        pixmap = QPixmap(model.file_path)
        if not pixmap.isNull():
            # 适应预览区域大小
            preview_size = self.preview_label.size()
            scaled = pixmap.scaled(
                preview_size.width() - 20,
                preview_size.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
            self.preview_label.setStyleSheet("QLabel { border: none; }")
        
        # 更新信息
        size_mb = model.file_size / (1024 * 1024)
        self.info_label.setText(
            f"{model.name} | {model.width}x{model.height} | {size_mb:.2f} MB | {model.file_type.upper()}"
        )
    
    def clear_all(self):
        """清空数据库和显示"""
        reply = QMessageBox.question(
            self, "确认", "确定清空所有图片记录吗？\n（不会删除原文件）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self.load_from_database()
            self.preview_label.clear()
            self.preview_label.setText("点击左侧图片预览\n或导入文件夹开始")
            self.preview_label.setStyleSheet("""
                QLabel {
                    background-color: #2d2d2d;
                    color: #888;
                    border: 2px dashed #555;
                    border-radius: 8px;
                }
            """)
            self.info_label.setText("已清空")
    
    def update_stats(self):
        """更新统计信息"""
        stats = self.db.get_stats()
        size_mb = stats["total_size"] / (1024 * 1024)
        self.stats_label.setText(f"图片: {stats['count']} | 总大小: {size_mb:.2f} MB")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("表情工坊 - Day3 数据库版")
        self.setMinimumSize(1000, 700)
        
        # 初始化数据库服务
        self.db_service = DatabaseService()
        
        # 设置中心部件
        self.gallery = GalleryView(self.db_service)
        self.setCentralWidget(self.gallery)
        
        # 状态栏
        self.statusBar().showMessage("Day3: 文件操作 + SQLite")
    
    def closeEvent(self, event):
        """关闭时清理"""
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 深色主题
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
        QListWidget {
            background-color: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
        }
        QLabel { color: #e0e0e0; }
    """)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())