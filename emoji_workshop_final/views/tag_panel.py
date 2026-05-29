from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QColorDialog,
    QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


class TagPanel(QWidget):
    """标签管理面板：添加/删除标签，支持多图批量打标签"""
    
    tag_selected = pyqtSignal(list)  # 发射选中的标签ID列表
    
    def __init__(self, db_service, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.current_image_ids: list = []   # 支持多选，存 id 列表
        self.setup_ui()
        self.load_tags()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # === 选中状态标签 ===
        self.selection_label = QLabel("未选中图片")
        self.selection_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.selection_label)
        
        # === 添加新标签 ===
        add_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("输入标签名...")
        self.color_btn = QPushButton("🎨")
        self.color_btn.setFixedWidth(40)
        self.color_btn.clicked.connect(self.pick_color)
        self.add_btn = QPushButton("➕ 添加")
        self.add_btn.clicked.connect(self.add_tag)
        
        add_layout.addWidget(self.tag_input)
        add_layout.addWidget(self.color_btn)
        add_layout.addWidget(self.add_btn)
        layout.addLayout(add_layout)
        
        # === 标签列表 ===
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.tag_list.itemSelectionChanged.connect(self.on_selection_changed)
        # 右键菜单
        self.tag_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tag_list.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(QLabel("所有标签（多选筛选）："))
        layout.addWidget(self.tag_list)
        
        # === 当前图片的标签 ===
        self.image_tags_label = QLabel("选中图片的标签：")
        layout.addWidget(self.image_tags_label)
        
        self.image_tag_list = QListWidget()
        self.image_tag_list.setMaximumHeight(100)
        layout.addWidget(self.image_tag_list)
        
        # === 给图片打标签 ===
        self.assign_btn = QPushButton("🏷️ 给选中图片打标签")
        self.assign_btn.setEnabled(False)
        self.assign_btn.clicked.connect(self.assign_tags_to_image)
        layout.addWidget(self.assign_btn)
        
        self.selected_color = "#FF6B6B"
        self.color_btn.setStyleSheet(f"background-color: {self.selected_color};")
    
    def pick_color(self):
        """选择标签颜色"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color.name()
            self.color_btn.setStyleSheet(f"background-color: {self.selected_color};")
    
    def add_tag(self):
        """添加新标签"""
        name = self.tag_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "标签名不能为空")
            return
        
        tag_id = self.db.add_tag(name, self.selected_color)
        self.tag_input.clear()
        self.load_tags()
    
    def load_tags(self):
        """加载所有标签"""
        self.tag_list.clear()
        rows = self.db.get_all_tags()
        for row in rows:
            tag_id, name, color = row
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, tag_id)
            item.setBackground(QColor(color))
            self.tag_list.addItem(item)
    
    def on_selection_changed(self):
        """标签选择变化时发射信号"""
        selected_ids = []
        for item in self.tag_list.selectedItems():
            selected_ids.append(item.data(Qt.ItemDataRole.UserRole))
        self.tag_selected.emit(selected_ids)
        
        # 如果有图片选中，启用打标签按钮
        self.assign_btn.setEnabled(bool(self.current_image_ids) and len(selected_ids) > 0)
    
    def set_current_images(self, image_ids: list):
        """设置当前选中的多张图片（支持多选）"""
        self.current_image_ids = image_ids
        n = len(image_ids)
        if n == 0:
            self.selection_label.setText("未选中图片")
        elif n == 1:
            self.selection_label.setText("已选中 1 张图片")
        else:
            self.selection_label.setText(f"已选中 {n} 张图片")
        
        self.load_image_tags_multi(image_ids)
        self.assign_btn.setEnabled(
            bool(self.current_image_ids) and
            len(self.tag_list.selectedItems()) > 0
        )
    
    def set_current_image(self, image_id: int):
        """向后兼容：设置单张图片"""
        self.set_current_images([image_id] if image_id is not None else [])
    
    def load_image_tags(self, image_id: int):
        """加载单张图片已有的标签（向后兼容）"""
        self.load_image_tags_multi([image_id] if image_id is not None else [])
    
    def load_image_tags_multi(self, image_ids: list):
        """加载多张图片的标签（显示所有图片共有标签）"""
        self.image_tag_list.clear()
        if not image_ids:
            return
        
        if len(image_ids) == 1:
            rows = self.db.get_image_tags(image_ids[0])
            for row in rows:
                tag_id, name, color = row
                item = QListWidgetItem(name)
                item.setBackground(QColor(color))
                self.image_tag_list.addItem(item)
        else:
            # 多选：显示"部分共有"的标签情况
            all_tag_sets = []
            for img_id in image_ids:
                rows = self.db.get_image_tags(img_id)
                all_tag_sets.append({row[0]: row for row in rows})
            
            # 统计每个标签在多少张图片中存在
            tag_counts: dict = {}
            for tag_set in all_tag_sets:
                for tag_id, row in tag_set.items():
                    if tag_id not in tag_counts:
                        tag_counts[tag_id] = {'row': row, 'count': 0}
                    tag_counts[tag_id]['count'] += 1
            
            total = len(image_ids)
            for tag_id, info in tag_counts.items():
                tag_id_, name, color = info['row']
                cnt = info['count']
                label = name if cnt == total else f"{name}（{cnt}/{total}）"
                item = QListWidgetItem(label)
                item.setBackground(QColor(color))
                self.image_tag_list.addItem(item)
    
    def assign_tags_to_image(self):
        """给当前所有选中图片批量添加选中的标签"""
        if not self.current_image_ids:
            return
        for item in self.tag_list.selectedItems():
            tag_id = item.data(Qt.ItemDataRole.UserRole)
            for img_id in self.current_image_ids:
                self.db.add_image_tag(img_id, tag_id)
        
        self.load_image_tags_multi(self.current_image_ids)
        n = len(self.current_image_ids)
        QMessageBox.information(self, "完成", f"已给 {n} 张图片添加标签")
    
    def show_context_menu(self, position):
        """右键删除标签"""
        item = self.tag_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        delete_action = menu.addAction("🗑️ 删除标签")
        action = menu.exec(self.tag_list.viewport().mapToGlobal(position))
        
        if action == delete_action:
            tag_id = item.data(Qt.ItemDataRole.UserRole)
            reply = QMessageBox.question(self, "确认", f"删除标签 '{item.text()}'？")
            if reply == QMessageBox.StandardButton.Yes:
                self.db.delete_tag(tag_id)
                self.load_tags()