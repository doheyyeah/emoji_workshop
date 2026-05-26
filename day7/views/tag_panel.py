from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QColorDialog,
    QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


class TagPanel(QWidget):
    """标签管理面板：添加/删除标签，给图片打标签"""
    
    tag_selected = pyqtSignal(list)  # 发射选中的标签ID列表
    
    def __init__(self, db_service, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.current_image_id = None
        self.setup_ui()
        self.load_tags()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
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
        self.assign_btn.setEnabled(self.current_image_id is not None and len(selected_ids) > 0)
    
    def set_current_image(self, image_id: int ):
        """设置当前选中的图片"""
        self.current_image_id = image_id
        self.load_image_tags(image_id)
        self.assign_btn.setEnabled(
            self.current_image_id is not None and 
            len(self.tag_list.selectedItems()) > 0
        )
    
    def load_image_tags(self, image_id: int ):
        """加载图片已有的标签"""
        if image_id is None:
            return
        self.image_tag_list.clear()
        rows = self.db.get_image_tags(image_id)
        for row in rows:
            tag_id, name, color = row
            item = QListWidgetItem(name)
            item.setBackground(QColor(color))
            self.image_tag_list.addItem(item)
    
    def assign_tags_to_image(self):
        """给当前图片添加选中的标签"""
        for item in self.tag_list.selectedItems():
            tag_id = item.data(Qt.ItemDataRole.UserRole)
            self.db.add_image_tag(self.current_image_id, tag_id)
        
        self.load_image_tags(self.current_image_id)
        QMessageBox.information(self, "完成", "标签已添加")
    
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