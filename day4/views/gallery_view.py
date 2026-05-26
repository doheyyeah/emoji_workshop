import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QFileDialog,
    QMessageBox, QSplitter, QProgressBar
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.database_service import DatabaseService
from services.thumbnail_service import ThumbnailService
from models.image_model import ImageModel
from utils.file_scanner import FileScanner


class ThumbnailWorker(QThread):
    """后台生成缩略图的工作线程"""
    progress = pyqtSignal(int, int)  # 当前进度, 总数
    finished = pyqtSignal()
    
    def __init__(self, thumb_service: ThumbnailService, image_models: list):
        super().__init__()
        self.thumb_service = thumb_service
        self.image_models = image_models
    
    def run(self):
        total = len(self.image_models)
        for i, model in enumerate(self.image_models):
            if not model.thumbnail_path or not Path(model.thumbnail_path).exists():
                thumb_path = self.thumb_service.get_thumbnail(model.file_path)
                if thumb_path:
                    model.thumbnail_path = thumb_path
            self.progress.emit(i + 1, total)
        self.finished.emit()


class GalleryView(QWidget):
    """图片画廊视图：支持缩略图缓存"""
    
    THUMBNAIL_SIZE = 128  # 列表中显示的缩略图尺寸
    
    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.thumb_service = ThumbnailService()
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
        
        self.stats_label = QLabel("图片: 0 | 总大小: 0 MB | 缓存: 0")
        
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.stats_label)
        
        layout.addLayout(toolbar)
        
        # === 进度条（导入时显示）===
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
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
        """导入文件夹中的图片到数据库（带缩略图生成）"""
        folder = QFileDialog.getExistingDirectory(self, "选择表情包文件夹")
        if not folder:
            return
        
        self.info_label.setText("正在扫描文件夹...")
        QApplication.processEvents()
        
        # 扫描图片
        images_info = FileScanner.scan_folder(folder)
        
        if not images_info:
            QMessageBox.information(self, "提示", "未找到支持的图片文件")
            return
        
        # 批量入库
        added_count = 0
        new_models = []
        for info in images_info:
            image_id = self.db.add_image(**info)
            if image_id:
                added_count += 1
                # 创建临时模型用于生成缩略图
                model = ImageModel(
                    id=image_id,
                    name=info['name'],
                    file_path=info['file_path'],
                    file_type=info['file_type'],
                    file_size=info['file_size'],
                    width=info['width'],
                    height=info['height']
                )
                new_models.append(model)
        
        self.info_label.setText(f"成功导入 {added_count} 张图片，正在生成缩略图...")
        
        # 后台生成缩略图
        self._generate_thumbnails_async(new_models)
    
    def _generate_thumbnails_async(self, models: list[ImageModel]):
        """异步生成缩略图，不卡UI"""
        self.progress_bar.setMaximum(len(models))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.import_btn.setEnabled(False)
        
        self.worker = ThumbnailWorker(self.thumb_service, models)
        self.worker.progress.connect(self._on_thumb_progress)
        self.worker.finished.connect(self._on_thumb_finished)
        self.worker.start()
    
    def _on_thumb_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.info_label.setText(f"生成缩略图: {current}/{total}")
    
    def _on_thumb_finished(self):
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)
        self.info_label.setText("缩略图生成完成")
        self.load_from_database()  # 刷新显示
        self.update_stats()
    
    def load_from_database(self):
        """从数据库加载所有图片显示（使用缩略图）"""
        self.list_widget.clear()
        self.current_images = []
        
        rows = self.db.get_all_images()
        for row in rows:
            model = ImageModel.from_db_row(row)
            self.current_images.append(model)
            self._add_thumbnail(model)
        
        self.update_stats()
    
    def _add_thumbnail(self, model: ImageModel):
        """添加缩略图到列表（优先用缓存，否则用原图缩放）"""
        item = QListWidgetItem()
        item.setText(model.display_name)
        item.setData(Qt.ItemDataRole.UserRole, model.id)
        
        # 优先尝试加载缩略图缓存
        thumb_path = None
        if model.thumbnail_path and Path(model.thumbnail_path).exists():
            thumb_path = model.thumbnail_path
        else:
            # 尝试生成/获取缓存
            thumb_path = self.thumb_service.get_thumbnail(model.file_path)
            if thumb_path:
                model.thumbnail_path = thumb_path
                # TODO: 可以在这里更新数据库的 thumbnail_path 字段
        
        # 加载图片
        if thumb_path:
            pixmap = QPixmap(thumb_path)
        else:
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
        """点击缩略图显示大图（加载原图）"""
        image_id = item.data(Qt.ItemDataRole.UserRole)
        model = next((m for m in self.current_images if m.id == image_id), None)
        
        if not model:
            return
        
        # 显示大图（加载原图）
        pixmap = QPixmap(model.file_path)
        if not pixmap.isNull():
            preview_size = self.preview_label.size()
            scaled = pixmap.scaled(
                preview_size.width() - 20,
                preview_size.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
            self.preview_label.setStyleSheet("QLabel { border: none; }")
        
        size_mb = model.file_size / (1024 * 1024)
        self.info_label.setText(
            f"{model.name} | {model.width}x{model.height} | {size_mb:.2f} MB | {model.file_type.upper()}"
        )
    
    def clear_all(self):
        """清空数据库和显示"""
        reply = QMessageBox.question(
            self, "确认", "确定清空所有图片记录吗？\n（不会删除原文件，但会清除缩略图缓存）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self.thumb_service.clear_cache()
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
        cache_count = self.thumb_service.get_cache_size()
        self.stats_label.setText(
            f"图片: {stats['count']} | 总大小: {size_mb:.2f} MB | 缓存: {cache_count}"
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("表情工坊 - Day4 缩略图缓存版")
        self.setMinimumSize(1000, 700)
        
        self.db_service = DatabaseService()
        self.gallery = GalleryView(self.db_service)
        self.setCentralWidget(self.gallery)
        
        self.statusBar().showMessage("Day4: Pillow缩略图 + 异步生成")
    
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