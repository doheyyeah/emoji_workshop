import sys
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QFileDialog,
    QMessageBox, QSplitter, QProgressBar, QComboBox, QAbstractItemView,
    QMenu
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QIcon

sys.path.insert(0, str(Path(__file__).parent.parent))
from services.database_service import DatabaseService
from services.thumbnail_service import ThumbnailService
from services.clipboard_service import ClipboardService
from models.image_model import ImageModel
from utils.file_scanner import FileScanner
from utils.config_manager import ConfigManager


class ThumbnailWorker(QThread):
    """后台生成缩略图的工作线程"""
    progress = pyqtSignal(int, int)
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
    """图片画廊视图：支持缩略图缓存 + 搜索筛选 + 拖拽导入 + 多选"""
    
    THUMBNAIL_SIZE = 128
    image_selected = pyqtSignal(int)          # 单图兼容信号（保留向后兼容）
    images_selection_changed = pyqtSignal(list)  # 多选信号，发出所有选中的 image_id 列表

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.thumb_service = ThumbnailService()
        self.config = ConfigManager()
        self.current_images: list[ImageModel] = []
        self._pending_models: list = []   # 拖拽/导入时暂存待生成缩略图的模型
        self.setAcceptDrops(True)
        self.setup_ui()
        self.load_from_database()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # === 搜索栏（带历史记录下拉框）===
        search_layout = QHBoxLayout()
        self.search_input = QComboBox()
        self.search_input.setEditable(True)
        self.search_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.search_input.lineEdit().setPlaceholderText("🔍 搜索表情包...")
        # 加载搜索历史
        for kw in self.config.get_search_history():
            self.search_input.addItem(kw)
        self.search_input.lineEdit().returnPressed.connect(self.do_search)

        self.search_btn = QPushButton("搜索")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.clicked.connect(self.do_search)
        self.reset_btn = QPushButton("重置")
        self.reset_btn.setObjectName("primaryButton")
        self.reset_btn.clicked.connect(self.load_from_database)
        self.clear_history_btn = QPushButton("清空搜索历史")
        self.clear_history_btn.setObjectName("primaryButton")
        self.clear_history_btn.setToolTip("清空搜索历史（只清历史，不清图片）")
        self.clear_history_btn.clicked.connect(self._clear_search_history)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.reset_btn)
        search_layout.addWidget(self.clear_history_btn)
        layout.addLayout(search_layout)
        
        # === 顶部工具栏 ===
        toolbar = QHBoxLayout()
        
        self.import_btn = QPushButton("📁 导入文件夹")
        self.import_btn.setObjectName("primaryButton")
        self.import_btn.setMinimumHeight(32)
        self.import_btn.clicked.connect(self.import_folder)
        
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setObjectName("dangerButton")
        self.clear_btn.clicked.connect(self.clear_all)
        
        self.stats_label = QLabel("图片: 0 | 总大小: 0 MB | 缓存: 0")
        
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.stats_label)
        
        layout.addLayout(toolbar)
        
        # === 进度条 ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # === 主区域 ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：缩略图列表（多选模式）
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("thumbList")
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setSpacing(10)
        self.list_widget.setMinimumWidth(400)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_image_context_menu)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        # 右侧：大图预览
        self.preview_label = QLabel("点击左侧图片预览\n或导入文件夹开始")
        self.preview_label.setObjectName("previewPane")
        self.preview_label.setProperty("hasImage", False)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 400)
        
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.preview_label)
        splitter.setSizes([500, 500])
        
        layout.addWidget(splitter)
        
        # === 底部信息栏 ===
        self.info_label = QLabel("就绪")
        layout.addWidget(self.info_label)
    
    def do_search(self):
        """按名称搜索，并记录历史"""
        keyword = self.search_input.currentText().strip()
        if not keyword:
            self.load_from_database()
            return
        
        # 记录搜索历史
        self.config.add_search_history(keyword)
        # 更新下拉列表
        self.search_input.clear()
        for kw in self.config.get_search_history():
            self.search_input.addItem(kw)
        self.search_input.lineEdit().setText(keyword)
        
        self.list_widget.clear()
        self.current_images = []
        
        rows = self.db.search_images_by_name(keyword)
        for row in rows:
            model = ImageModel.from_db_row(row)
            self.current_images.append(model)
            self._add_thumbnail(model)
        
        self.info_label.setText(f"搜索 '{keyword}' 找到 {len(rows)} 张")
        self.update_stats()
    
    def _clear_search_history(self):
        """清空搜索历史"""
        history = self.config.get_search_history()
        n = len(history)
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确认清空 {n} 条搜索历史？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.config.clear_search_history()
        self.search_input.clear()
        self.search_input.lineEdit().setPlaceholderText("🔍 搜索表情包...")
    
    def import_folder(self):
        """导入文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择表情包文件夹")
        if not folder:
            return
        
        self._pending_models = []
        added_count = self.import_folder_path(folder)
        # 记录最近文件夹
        self.config.add_recent_folder(folder)
        
        if added_count == 0:
            QMessageBox.information(self, "提示", "未找到支持的图片文件（或文件已全部存在）")
            return
        
        self.info_label.setText(f"成功导入 {added_count} 张图片，正在生成缩略图...")
        self._generate_thumbnails_async(self._pending_models)
    
    def import_folder_path(self, folder: str) -> int:
        """内部方法：扫描文件夹并入库，返回导入数量"""
        self.info_label.setText("正在扫描文件夹...")
        QApplication.processEvents()
        
        images_info = FileScanner.scan_folder(folder)
        
        if not images_info:
            return 0
        
        added_count = 0
        self._pending_models = []
        for info in images_info:
            image_id = self.db.add_image(**info)
            if image_id:
                added_count += 1
                model = ImageModel(
                    id=image_id,
                    name=info['name'],
                    file_path=info['file_path'],
                    file_type=info['file_type'],
                    file_size=info['file_size'],
                    width=info['width'],
                    height=info['height']
                )
                self._pending_models.append(model)
        return added_count
    
    def _import_single_image(self, file_path: str) -> bool:
        """导入单张图片，返回是否成功"""
        info = FileScanner.get_image_info(file_path)
        if not info:
            return False
        image_id = self.db.add_image(**info)
        return image_id is not None
    
    def _generate_thumbnails_async(self, models: list):
        """异步生成缩略图"""
        if not models:
            self.load_from_database()
            return
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
        self.load_from_database()
        self.update_stats()
    
    def load_from_database(self):
        """加载所有图片"""
        self.list_widget.clear()
        self.current_images = []
        
        rows = self.db.get_all_images()
        for row in rows:
            model = ImageModel.from_db_row(row)
            self.current_images.append(model)
            self._add_thumbnail(model)
        
        self.update_stats()
    
    def _add_thumbnail(self, model: ImageModel):
        """添加缩略图"""
        item = QListWidgetItem()
        item.setText(model.display_name)
        item.setData(Qt.ItemDataRole.UserRole, model.id)
        
        thumb_path = None
        if model.thumbnail_path and Path(model.thumbnail_path).exists():
            thumb_path = model.thumbnail_path
        else:
            thumb_path = self.thumb_service.get_thumbnail(model.file_path)
            if thumb_path:
                model.thumbnail_path = thumb_path
        
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
        """点击缩略图（保留向后兼容）"""
        image_id = item.data(Qt.ItemDataRole.UserRole)
        model = next((m for m in self.current_images if m.id == image_id), None)
        
        if not model:
            return
        
        # 显示大图
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
            self.preview_label.setProperty("hasImage", True)
            self.preview_label.style().unpolish(self.preview_label)
            self.preview_label.style().polish(self.preview_label)
        
        size_mb = model.file_size / (1024 * 1024)
        self.info_label.setText(
            f"{model.name} | {model.width}x{model.height} | {size_mb:.2f} MB | {model.file_type.upper()}"
        )
    
    def _on_selection_changed(self):
        """多选变化时发射信号，并更新预览"""
        selected_items = self.list_widget.selectedItems()
        selected_ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        # 发射多选信号
        self.images_selection_changed.emit(selected_ids)
        
        # 向后兼容：单选时也发射 image_selected
        if len(selected_ids) == 1:
            self.image_selected.emit(selected_ids[0])
            # 更新预览
            model = next((m for m in self.current_images if m.id == selected_ids[0]), None)
            if model:
                self.on_item_clicked(selected_items[0])
        elif len(selected_ids) > 1:
            self.info_label.setText(f"已选中 {len(selected_ids)} 张图片")
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击复制图片到剪贴板"""
        image_id = item.data(Qt.ItemDataRole.UserRole)
        model = next((m for m in self.current_images if m.id == image_id), None)
        if not model:
            return
        
        if ClipboardService.copy_image(model.file_path):
            self.db.record_usage(image_id)
            msg = "已复制 + 已记录使用"
            # 通知主窗口在状态栏显示
            main_win = self.window()
            if hasattr(main_win, 'statusBar'):
                main_win.statusBar().showMessage(msg, 2000)

    def _show_image_context_menu(self, position):
        """缩略图右键菜单：支持删除选中的图片库记录。"""
        item = self.list_widget.itemAt(position)
        if item and not item.isSelected():
            self.list_widget.setCurrentItem(item)

        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("🗑️ 删除选中图片")
        action = menu.exec(self.list_widget.viewport().mapToGlobal(position))
        if action == delete_action:
            self._delete_selected_images()

    def _delete_selected_images(self):
        """删除选中的图片库记录；默认不删除原图文件，只删除库记录和关联标签。"""
        selected_items = self.list_widget.selectedItems()
        image_ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        image_ids = [image_id for image_id in image_ids if image_id is not None]
        if not image_ids:
            return

        count = len(image_ids)
        reply = QMessageBox.question(
            self,
            "删除图片记录",
            f"确定从图片库删除选中的 {count} 张图片吗？\n\n"
            "这会删除图片库记录和标签关联，不会删除原始图片文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        for image_id in image_ids:
            if self.db.delete_image(image_id):
                deleted += 1

        self.load_from_database()
        self.preview_label.clear()
        self.preview_label.setText("点击左侧图片预览\n或导入文件夹开始")
        self.preview_label.setProperty("hasImage", False)
        self.preview_label.style().unpolish(self.preview_label)
        self.preview_label.style().polish(self.preview_label)
        self.info_label.setText(f"已删除 {deleted} 张图片记录")
        self.images_selection_changed.emit([])
        main_win = self.window()
        if hasattr(main_win, 'statusBar'):
            main_win.statusBar().showMessage(f"已删除 {deleted} 张图片记录", 2000)
    
    # ------------------------------------------------------------------
    # 拖拽导入（Task 1）
    # ------------------------------------------------------------------
    
    def dragEnterEvent(self, event):
        """接受含 URL 的拖拽事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """处理拖拽放入：文件夹或图片文件均可"""
        supported_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
        urls = event.mimeData().urls()
        
        added_count = 0
        folder_count = 0
        file_count = 0
        all_models = []
        
        for url in urls:
            local_path = url.toLocalFile()
            path = Path(local_path)
            
            if path.is_dir():
                # 文件夹：批量扫描
                count = self.import_folder_path(str(path))
                added_count += count
                folder_count += 1
                all_models.extend(getattr(self, '_pending_models', []))
                self.config.add_recent_folder(str(path))
            elif path.is_file() and path.suffix.lower() in supported_exts:
                # 单张图片
                if self._import_single_image(str(path)):
                    added_count += 1
                    file_count += 1
        
        if added_count > 0:
            msg_parts = []
            if folder_count > 0:
                msg_parts.append(f"{folder_count} 个文件夹")
            if file_count > 0:
                msg_parts.append(f"{file_count} 个文件")
            self.info_label.setText(f"已导入 {added_count} 张图片（来自 {'、'.join(msg_parts)}）")
            
            if all_models:
                self._generate_thumbnails_async(all_models)
            else:
                self.load_from_database()
            
            # 在主窗口状态栏提示
            main_win = self.window()
            if hasattr(main_win, 'statusBar'):
                main_win.statusBar().showMessage(f"已导入 {added_count} 张图片", 3000)
        else:
            self.load_from_database()
            self.info_label.setText("拖入完成，未发现新图片（可能已存在）")
    
    def filter_by_tags(self, tag_ids: List[int]):
        """按标签筛选（Day5 新增）"""
        if not tag_ids:
            self.load_from_database()
            return
        
        self.list_widget.clear()
        self.current_images = []
        
        rows = self.db.search_images_by_tags(tag_ids)
        for row in rows:
            model = ImageModel.from_db_row(row)
            self.current_images.append(model)
            self._add_thumbnail(model)
        
        self.info_label.setText(f"标签筛选: {len(rows)} 张")
        self.update_stats()

    def filter_by_tag_names(self, tag_names: List[str], match_mode: str = "union"):
        """按标签名筛选，支持并集/交集"""
        if not tag_names:
            self.load_from_database()
            return

        self.list_widget.clear()
        self.current_images = []

        if match_mode == "intersect":
            rows = self.db.get_images_by_tags_intersect(tag_names)
        else:
            rows = self.db.get_images_by_tags_union(tag_names)

        for row in rows:
            model = ImageModel.from_db_row(
                (
                    row["id"],
                    row["name"],
                    row["file_path"],
                    row["file_type"],
                    row["file_size"],
                    row["width"],
                    row["height"],
                    row.get("thumbnail_path"),
                )
            )
            self.current_images.append(model)
            self._add_thumbnail(model)

        mode_cn = "交集" if match_mode == "intersect" else "并集"
        self.info_label.setText(f"标签筛选（{mode_cn}）: {len(rows)} 张")
        self.update_stats()
    
    def clear_all(self):
        """清空"""
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
            self.preview_label.setProperty("hasImage", False)
            self.preview_label.style().unpolish(self.preview_label)
            self.preview_label.style().polish(self.preview_label)
            self.info_label.setText("已清空")
    
    def update_stats(self):
        """更新统计"""
        stats = self.db.get_stats()
        size_mb = stats["total_size"] / (1024 * 1024)
        cache_count = self.thumb_service.get_cache_size()
        self.stats_label.setText(
            f"图片: {stats['count']} | 总大小: {size_mb:.2f} MB | 缓存: {cache_count}"
        )
