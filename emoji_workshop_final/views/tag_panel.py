from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QColorDialog,
    QMessageBox, QMenu, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


class TagPanel(QWidget):
    """标签管理面板：筛选模式 + 打标签模式"""

    # 兼容保留：对外发射已选标签ID（筛选模式时）
    tag_selected = pyqtSignal(list)
    # 新信号：发射标签名 + 并/交模式
    filter_tags_changed = pyqtSignal(list, str)
    # 标签更新后通知外部刷新
    tags_updated = pyqtSignal()

    def __init__(self, db_service, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.current_image_ids: list = []
        self._last_nonempty_selection: list = []  # 缓存上一次非空选中列表，防止失焦时清空
        self.mode = "filter"      # filter | tagging
        self.match_mode = "union"  # union | intersect
        self.setup_ui()
        self.load_tags()
        self._update_mode_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # === 模式切换 ===
        # 原来「筛选模式 / 打标签模式 / 并集 / 交集」全部挤在同一行，
        # 右侧面板较窄时会把“打标签模式”的最后一个字遮住。
        # 拆成两行后，模式选择和筛选逻辑选择互不挤压。
        mode_layout = QHBoxLayout()
        self.filter_mode_radio = QRadioButton("🔍 筛选模式")
        self.tag_mode_radio = QRadioButton("✏️ 打标签模式")
        self.filter_mode_radio.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.filter_mode_radio)
        self.mode_group.addButton(self.tag_mode_radio)
        self.filter_mode_radio.toggled.connect(self._on_mode_changed)

        mode_layout.addWidget(self.filter_mode_radio)
        mode_layout.addWidget(self.tag_mode_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        match_layout = QHBoxLayout()
        match_layout.addStretch()
        self.union_radio = QRadioButton("并集")
        self.intersect_radio = QRadioButton("交集")
        self.union_radio.setChecked(True)
        self.union_radio.toggled.connect(self._on_match_mode_changed)
        match_layout.addWidget(self.union_radio)
        match_layout.addWidget(self.intersect_radio)
        layout.addLayout(match_layout)

        self.mode_hint_label = QLabel("已选中 0 个标签作筛选条件")
        self.mode_hint_label.setObjectName("hintLabel")
        layout.addWidget(self.mode_hint_label)

        # === 选中状态标签 ===
        self.selection_label = QLabel("未选中图片")
        self.selection_label.setObjectName("hintLabel")
        layout.addWidget(self.selection_label)

        # === 添加新标签 ===
        add_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("输入标签名...")
        self.color_btn = QPushButton("🎨")
        self.color_btn.setObjectName("secondaryButton")
        self.color_btn.setFixedWidth(40)
        self.color_btn.clicked.connect(self.pick_color)
        self.add_btn = QPushButton("➕ 添加")
        self.add_btn.setObjectName("primaryButton")
        self.add_btn.clicked.connect(self.add_tag)
        add_layout.addWidget(self.tag_input)
        add_layout.addWidget(self.color_btn)
        add_layout.addWidget(self.add_btn)
        layout.addLayout(add_layout)

        # === 标签列表 ===
        self.tag_list = QListWidget()
        self.tag_list.setObjectName("tagList")
        self.tag_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.tag_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.tag_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tag_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(QLabel("所有标签："))
        layout.addWidget(self.tag_list)

        # === 当前图片标签 ===
        self.image_tags_label = QLabel("选中图片的标签：")
        layout.addWidget(self.image_tags_label)
        self.image_tag_list = QListWidget()
        self.image_tag_list.setObjectName("imageTagList")
        self.image_tag_list.setMaximumHeight(100)
        layout.addWidget(self.image_tag_list)

        # === 给图片打标签 ===
        self.assign_btn = QPushButton("🏷️ 添加到选中图片")
        self.assign_btn.setObjectName("primaryButton")
        self.assign_btn.setEnabled(False)
        self.assign_btn.clicked.connect(self.assign_tags_to_image)
        layout.addWidget(self.assign_btn)

        self.selected_color = "#FF6B6B"
        self.color_btn.setStyleSheet(f"background-color: {self.selected_color};")

    def pick_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color.name()
            self.color_btn.setStyleSheet(f"background-color: {self.selected_color};")

    def add_tag(self):
        name = self.tag_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "标签名不能为空")
            return
        self.db.add_tag(name, self.selected_color)
        self.tag_input.clear()
        self.load_tags()

    def load_tags(self):
        self.tag_list.clear()
        rows = self.db.get_all_tags()
        for row in rows:
            tag_id, name, color = row
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, tag_id)
            item.setBackground(QColor(color))
            self.tag_list.addItem(item)

    def _selected_tag_items(self):
        return self.tag_list.selectedItems()

    def _selected_tag_ids(self):
        return [item.data(Qt.ItemDataRole.UserRole) for item in self._selected_tag_items()]

    def _selected_tag_names(self):
        return [item.text() for item in self._selected_tag_items()]

    def _on_mode_changed(self):
        self.mode = "filter" if self.filter_mode_radio.isChecked() else "tagging"
        self._update_mode_ui()
        self.on_selection_changed()

    def _on_match_mode_changed(self):
        self.match_mode = "union" if self.union_radio.isChecked() else "intersect"
        if self.mode == "filter":
            self.on_selection_changed()

    def _update_mode_ui(self):
        is_filter = self.mode == "filter"
        self.union_radio.setEnabled(is_filter)
        self.intersect_radio.setEnabled(is_filter)
        self.assign_btn.setVisible(not is_filter)
        self._update_hint_text()
        self.assign_btn.setEnabled(
            (not is_filter)
            and bool(self.current_image_ids)
            and len(self._selected_tag_items()) > 0
        )

    def _update_hint_text(self):
        if self.mode == "filter":
            self.mode_hint_label.setText(
                f"已选中 {len(self._selected_tag_items())} 个标签作筛选条件"
            )
        else:
            self.mode_hint_label.setText(
                f"将批量操作 {len(self.current_image_ids)} 张选中图片"
            )

    def on_selection_changed(self):
        selected_ids = self._selected_tag_ids()
        selected_names = self._selected_tag_names()
        self._update_hint_text()

        if self.mode == "filter":
            self.tag_selected.emit(selected_ids)
            self.filter_tags_changed.emit(selected_names, self.match_mode)
        else:
            self.assign_btn.setEnabled(bool(self.current_image_ids) and len(selected_ids) > 0)

    def set_current_images(self, image_ids: list):
        """更新当前选中图片列表。若新列表非空则同步更新缓存；为空时保留缓存（防止失焦清空）。"""
        self.current_image_ids = image_ids
        if image_ids:
            self._last_nonempty_selection = list(image_ids)
        n = len(image_ids)
        if n == 0:
            self.selection_label.setText("未选中图片")
        elif n == 1:
            self.selection_label.setText("已选中 1 张图片")
        else:
            self.selection_label.setText(f"已选中 {n} 张图片")

        self.load_image_tags_multi(image_ids)
        self._update_mode_ui()

    def clear_selection(self):
        """明确清空缓存（由 GalleryView 在用户点击空白处或按 Esc 时调用）。"""
        self.current_image_ids = []
        self._last_nonempty_selection = []
        self.selection_label.setText("未选中图片")
        self.image_tag_list.clear()
        self._update_mode_ui()

    def set_current_image(self, image_id: int):
        self.set_current_images([image_id] if image_id is not None else [])

    def load_image_tags(self, image_id: int):
        self.load_image_tags_multi([image_id] if image_id is not None else [])

    def load_image_tags_multi(self, image_ids: list):
        self.image_tag_list.clear()
        if not image_ids:
            return

        if len(image_ids) == 1:
            rows = self.db.get_image_tags(image_ids[0])
            for row in rows:
                _, name, color = row
                item = QListWidgetItem(name)
                item.setBackground(QColor(color))
                self.image_tag_list.addItem(item)
            return

        all_tag_sets = []
        for img_id in image_ids:
            rows = self.db.get_image_tags(img_id)
            all_tag_sets.append({row[0]: row for row in rows})

        tag_counts: dict = {}
        for tag_set in all_tag_sets:
            for tag_id, row in tag_set.items():
                if tag_id not in tag_counts:
                    tag_counts[tag_id] = {"row": row, "count": 0}
                tag_counts[tag_id]["count"] += 1

        total = len(image_ids)
        for _, info in tag_counts.items():
            _, name, color = info["row"]
            cnt = info["count"]
            label = name if cnt == total else f"{name}（{cnt}/{total}）"
            item = QListWidgetItem(label)
            item.setBackground(QColor(color))
            self.image_tag_list.addItem(item)

    def assign_tags_to_image(self):
        ids = self._last_nonempty_selection
        if not ids:
            QMessageBox.information(self, "提示", "请先在画廊中选中至少 1 张图片")
            return

        selected_names = self._selected_tag_names()
        typed_name = self.tag_input.text().strip()
        if typed_name and typed_name not in selected_names:
            selected_names.append(typed_name)
        if not selected_names:
            QMessageBox.warning(self, "提示", "请先选择标签")
            return

        for tag_name in selected_names:
            for image_id in ids:
                self.db.add_tag_to_image(image_id, tag_name)

        tag_name_for_msg = selected_names[0] if len(selected_names) == 1 else "、".join(selected_names)
        self.tag_input.clear()
        self.load_tags()

        self.load_image_tags_multi(self.current_image_ids)
        self._refresh_selection_from_current_images()
        self.tags_updated.emit()
        QMessageBox.information(
            self, "完成",
            f"已给 {len(ids)} 张图片打标签『{tag_name_for_msg}』"
        )

    def _refresh_selection_from_current_images(self):
        if not self.current_image_ids:
            return
        common_tag_ids = None
        for image_id in self.current_image_ids:
            tag_ids = {row[0] for row in self.db.get_image_tags(image_id)}
            common_tag_ids = tag_ids if common_tag_ids is None else (common_tag_ids & tag_ids)
        common_tag_ids = common_tag_ids or set()

        self.tag_list.blockSignals(True)
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            tag_id = item.data(Qt.ItemDataRole.UserRole)
            item.setSelected(tag_id in common_tag_ids)
        self.tag_list.blockSignals(False)
        self.on_selection_changed()

    def show_context_menu(self, position):
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
                self.tags_updated.emit()
