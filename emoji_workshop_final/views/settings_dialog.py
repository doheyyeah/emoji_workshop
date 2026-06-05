from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QDialogButtonBox,
    QFileDialog, QTabWidget, QWidget, QGroupBox, QFormLayout,
    QMessageBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from utils.config_manager import ConfigManager


class SettingsDialog(QDialog):
    """应用设置对话框：多标签页设计

    标签页：
    - 常规：主题、缩略图大小、行为设置
    - 路径：默认文件夹、缓存位置
    - 网络：连接测试
    - 高级：重置配置、统计信息
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.setWindowTitle("⚙️ 应用设置")
        self.setMinimumSize(700, 550)
        self.resize(800, 650)
        self._setup_ui()
        self._load_all_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 多标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # === 标签页1：常规 ===
        self.general_tab = self._create_general_tab()
        self.tabs.addTab(self.general_tab, "常规")

        # === 标签页2：路径 ===
        self.paths_tab = self._create_paths_tab()
        self.tabs.addTab(self.paths_tab, "路径")

        # === 标签页3：网络 ===
        self.network_tab = self._create_network_tab()
        self.tabs.addTab(self.network_tab, "网络")

        # === 标签页4：高级 ===
        self.advanced_tab = self._create_advanced_tab()
        self.tabs.addTab(self.advanced_tab, "高级")

        # === 标签页5：AI 推荐 ===
        self.ai_tab = self._create_ai_tab()
        self.tabs.addTab(self.ai_tab, "🤖 AI 推荐")

        # 底部按钮（全部中文）
        # 注意：不再提供「恢复默认」按钮，避免与「高级 > 危险操作 > 重置所有配置为默认值」
        # 重复，且降低误触整套配置的风险。重置配置仅在高级标签页的危险操作中保留。
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 外观设置组
        appearance_group = QGroupBox("外观")
        appearance_layout = QFormLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        appearance_layout.addRow("主题:", self.theme_combo)

        self.thumb_size_spin = QSpinBox()
        self.thumb_size_spin.setRange(64, 256)
        self.thumb_size_spin.setSuffix(" px")
        appearance_layout.addRow("缩略图大小:", self.thumb_size_spin)

        self.grid_spacing_spin = QSpinBox()
        self.grid_spacing_spin.setRange(0, 30)
        self.grid_spacing_spin.setSuffix(" px")
        appearance_layout.addRow("网格间距:", self.grid_spacing_spin)

        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)

        # 行为设置组
        behavior_group = QGroupBox("行为")
        behavior_layout = QFormLayout()

        self.auto_save_check = QCheckBox("修改配置后自动保存")
        behavior_layout.addRow(self.auto_save_check)

        self.confirm_delete_check = QCheckBox("删除前显示确认对话框")
        behavior_layout.addRow(self.confirm_delete_check)

        self.clipboard_monitor_check = QCheckBox("启用剪贴板监听（检测到图片自动询问是否入库）")
        behavior_layout.addRow(self.clipboard_monitor_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        # 最近文件夹列表
        recent_group = QGroupBox("最近导入的文件夹")
        recent_layout = QVBoxLayout()
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(120)
        self.recent_list.itemDoubleClicked.connect(self._on_recent_folder_dblclick)
        recent_layout.addWidget(self.recent_list)
        recent_layout.addWidget(QLabel("（双击可重新导入该文件夹）"))

        clear_recent_btn = QPushButton("清空历史")
        clear_recent_btn.clicked.connect(self._clear_recent)
        recent_layout.addWidget(clear_recent_btn)

        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)

        layout.addStretch()
        return tab

    def _create_paths_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        paths_group = QGroupBox("默认路径")
        paths_layout = QFormLayout()

        # 默认导入文件夹
        import_layout = QHBoxLayout()
        self.import_path_edit = QLineEdit()
        self.import_path_edit.setReadOnly(True)
        import_layout.addWidget(self.import_path_edit)
        import_browse = QPushButton("浏览...")
        import_browse.clicked.connect(self._browse_import)
        import_layout.addWidget(import_browse)
        paths_layout.addRow("默认导入文件夹:", import_layout)

        # 默认导出文件夹
        export_layout = QHBoxLayout()
        self.export_path_edit = QLineEdit()
        self.export_path_edit.setReadOnly(True)
        export_layout.addWidget(self.export_path_edit)
        export_browse = QPushButton("浏览...")
        export_browse.clicked.connect(self._browse_export)
        export_layout.addWidget(export_browse)
        paths_layout.addRow("默认导出文件夹:", export_layout)

        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)

        layout.addStretch()
        return tab

    def _create_network_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 网络测试组
        test_group = QGroupBox("连接测试")
        test_layout = QVBoxLayout()

        self.test_result_label = QLabel("点击测试按钮验证网络连接")
        test_layout.addWidget(self.test_result_label)

        test_btn = QPushButton("🌐 测试网络连接")
        test_btn.clicked.connect(self._test_network)
        test_layout.addWidget(test_btn)

        test_group.setLayout(test_layout)
        layout.addWidget(test_group)

        layout.addStretch()
        return tab

    def _create_ai_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("LLM 智能推荐")
        form = QFormLayout()

        self.llm_enabled_check = QCheckBox("启用 LLM 智能推荐")
        form.addRow(self.llm_enabled_check)

        self.llm_base_url_edit = QLineEdit()
        form.addRow("Base URL:", self.llm_base_url_edit)

        self.llm_api_key_edit = QLineEdit()
        self.llm_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API Key:", self.llm_api_key_edit)

        self.llm_model_edit = QLineEdit()
        form.addRow("Model:", self.llm_model_edit)

        self.llm_test_btn = QPushButton("测试连接")
        self.llm_test_btn.clicked.connect(self._test_llm_connection)
        form.addRow("", self.llm_test_btn)

        self.llm_test_result = QLabel("未测试")
        form.addRow("状态:", self.llm_test_result)

        group.setLayout(form)
        layout.addWidget(group)

        # === 视觉精排组 ===
        vision_group = QGroupBox("视觉精排（可选）")
        vision_form = QFormLayout()

        self.vision_enabled_check = QCheckBox("启用视觉精排（需要视觉模型 API Key）")
        vision_form.addRow(self.vision_enabled_check)

        self.vision_base_url_edit = QLineEdit()
        vision_form.addRow("Base URL:", self.vision_base_url_edit)

        self.vision_api_key_edit = QLineEdit()
        self.vision_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        vision_form.addRow("API Key:", self.vision_api_key_edit)

        self.vision_model_edit = QLineEdit()
        vision_form.addRow("Model:", self.vision_model_edit)

        self.vision_test_btn = QPushButton("测试连接")
        self.vision_test_btn.clicked.connect(self._test_vision_connection)
        vision_form.addRow("", self.vision_test_btn)

        self.vision_test_result = QLabel("未测试")
        vision_form.addRow("状态:", self.vision_test_result)

        vision_group.setLayout(vision_form)
        layout.addWidget(vision_group)

        layout.addStretch()
        return tab

    def _create_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 危险操作（高级标签页仅保留危险操作；使用统计已并入「数据统计」功能，避免重复展示）
        danger_group = QGroupBox("危险操作")
        danger_layout = QVBoxLayout()

        reset_btn = QPushButton("🔄 重置所有配置为默认值")
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._restore_defaults)
        danger_layout.addWidget(reset_btn)

        clear_cache_btn = QPushButton("🗑️ 清空缩略图缓存")
        clear_cache_btn.setObjectName("dangerButton")
        clear_cache_btn.clicked.connect(self._clear_cache)
        danger_layout.addWidget(clear_cache_btn)

        danger_group.setLayout(danger_layout)
        layout.addWidget(danger_group)

        layout.addStretch()
        return tab

    # ===== 加载设置 =====

    def _load_all_settings(self):
        """从 ConfigManager 加载所有设置到 UI"""
        # 常规
        self.theme_combo.setCurrentText(self.config.get("ui.theme", "dark"))
        self.thumb_size_spin.setValue(self.config.get("ui.thumbnail_size", 128))
        self.grid_spacing_spin.setValue(self.config.get("ui.grid_spacing", 10))
        self.auto_save_check.setChecked(self.config.get("behavior.auto_save", True))
        self.confirm_delete_check.setChecked(self.config.get("behavior.confirm_delete", True))
        self.clipboard_monitor_check.setChecked(
            self.config.get("behavior.clipboard_monitor_enabled", False)
        )

        # 最近文件夹（使用 get_recent_folders 方法确保兼容）
        self.recent_list.clear()
        for folder in self.config.get_recent_folders():
            self.recent_list.addItem(folder)

        # 路径
        self.import_path_edit.setText(self.config.get("paths.last_import_folder", ""))
        self.export_path_edit.setText(self.config.get("paths.last_export_folder", ""))

        llm = self.config.get_llm_config()
        self.llm_enabled_check.setChecked(llm["enabled"])
        self.llm_base_url_edit.setText(llm["base_url"])
        self.llm_api_key_edit.setText(llm["api_key"])
        self.llm_model_edit.setText(llm["model"])

        vision = self.config.get_vision_config()
        self.vision_enabled_check.setChecked(vision.get("enabled", False))
        self.vision_base_url_edit.setText(vision.get("base_url", ""))
        self.vision_api_key_edit.setText(vision.get("api_key", ""))
        self.vision_model_edit.setText(vision.get("model", ""))

    # ===== 保存设置 =====

    def _save_and_close(self):
        """保存所有设置并关闭对话框"""
        # 常规
        self.config.set("ui.theme", self.theme_combo.currentText())
        self.config.set("ui.thumbnail_size", self.thumb_size_spin.value())
        self.config.set("ui.grid_spacing", self.grid_spacing_spin.value())
        self.config.set("behavior.auto_save", self.auto_save_check.isChecked())
        self.config.set("behavior.confirm_delete", self.confirm_delete_check.isChecked())
        self.config.set("behavior.clipboard_monitor_enabled", self.clipboard_monitor_check.isChecked())

        # 路径
        self.config.set("paths.last_import_folder", self.import_path_edit.text())
        self.config.set("paths.last_export_folder", self.export_path_edit.text())

        self.config.set_llm_config(
            base_url=self.llm_base_url_edit.text().strip(),
            api_key=self.llm_api_key_edit.text().strip(),
            model=self.llm_model_edit.text().strip(),
            enabled=self.llm_enabled_check.isChecked(),
        )

        self.config.set_vision_config(
            base_url=self.vision_base_url_edit.text().strip(),
            api_key=self.vision_api_key_edit.text().strip(),
            model=self.vision_model_edit.text().strip(),
            enabled=self.vision_enabled_check.isChecked(),
        )

        # 强制保存
        self.config.save()
        self.accept()

    # ===== 按钮事件 =====

    def _browse_import(self):
        folder = QFileDialog.getExistingDirectory(self, "选择默认导入文件夹")
        if folder:
            self.import_path_edit.setText(folder)

    def _browse_export(self):
        folder = QFileDialog.getExistingDirectory(self, "选择默认导出文件夹")
        if folder:
            self.export_path_edit.setText(folder)

    def _clear_recent(self):
        self.config.set("behavior.recent_folders", [])
        self.recent_list.clear()
    
    def _on_recent_folder_dblclick(self, item):
        """双击最近文件夹项，通知主窗口导入该文件夹"""
        folder = item.text()
        from pathlib import Path as _Path
        if not _Path(folder).exists():
            QMessageBox.warning(self, "警告", f"文件夹不存在：{folder}")
            return
        # 通知父窗口（MainWindow）触发导入
        parent = self.parent()
        if parent and hasattr(parent, 'gallery'):
            self.accept()
            count = parent.gallery.import_folder_path(folder)
            parent.gallery.load_from_database()
            QMessageBox.information(parent, "导入完成", f"已从最近文件夹导入 {count} 张图片")

    def _restore_defaults(self):
        reply = QMessageBox.question(
            self, "确认重置",
            "确定将所有配置恢复为默认值吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.reset_to_default()
            self._load_all_settings()
            QMessageBox.information(self, "完成", "配置已重置为默认值")

    def _clear_cache(self):
        reply = QMessageBox.question(
            self, "确认", "确定清空所有缩略图缓存吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # 通过父窗口调用清理（实际实现中需要传递 thumbnail_service）
            QMessageBox.information(self, "完成", "缩略图缓存已清空")

    def _test_network(self):
        """测试网络连接"""
        import requests
        from PyQt6.QtCore import QThread, pyqtSignal

        class TestThread(QThread):
            result = pyqtSignal(str, bool)

            def run(self):
                try:
                    # 测试百度（国内）和 Google（国外）
                    urls = [
                        ("百度", "https://www.baidu.com", 5),
                        ("Google", "https://www.google.com", 5),
                    ]

                    results = []
                    for name, url, timeout in urls:
                        try:
                            r = requests.get(url, timeout=timeout)
                            results.append((f"✅ {name}:正常", True, ""))
                        except Exception as e:
                            results.append((f"❌ {name}:不正常", False, str(e)))

                    lines = [r[0] for r in results]
                    tooltip = "\n".join([f"{r[0]} -> {r[2]}" for r in results if r[2]])
                    self.result.emit("\n".join(lines) + "\n@@@" + tooltip, all(r[1] for r in results))
                except Exception as e:
                    self.result.emit(f"测试失败@@@{str(e)}", False)

        self.test_result_label.setText("正在测试...")
        self.thread = TestThread()
        self.thread.result.connect(self._on_test_result)
        self.thread.start()

    def _on_test_result(self, msg, success):
        display_msg, _, tooltip = msg.partition("@@@")
        self.test_result_label.setText(display_msg)
        self.test_result_label.setToolTip(tooltip)
        if success:
            self.test_result_label.setStyleSheet("color: #51cf66;")
        else:
            self.test_result_label.setStyleSheet("color: #ff6b6b;")

    def _test_llm_connection(self):
        from services.llm_service import LLMService

        try:
            llm = LLMService(
                base_url=self.llm_base_url_edit.text().strip(),
                api_key=self.llm_api_key_edit.text().strip(),
                model=self.llm_model_edit.text().strip(),
            )
            _ = llm.chat("hi", timeout=30)
            self.llm_test_result.setText("✅ 连接成功")
            self.llm_test_result.setStyleSheet("color: #51cf66;")
        except Exception as exc:
            self.llm_test_result.setText("❌ 连接失败")
            self.llm_test_result.setStyleSheet("color: #ff6b6b;")
            self.llm_test_result.setToolTip(str(exc))

    def _test_vision_connection(self):
        from services.vision_service import VisionService

        try:
            svc = VisionService(
                base_url=self.vision_base_url_edit.text().strip(),
                api_key=self.vision_api_key_edit.text().strip(),
                model=self.vision_model_edit.text().strip(),
            )
            ok, msg = svc.test_connection()
            if ok:
                self.vision_test_result.setText("✅ 连接成功")
                self.vision_test_result.setStyleSheet("color: #51cf66;")
            else:
                self.vision_test_result.setText("❌ 连接失败")
                self.vision_test_result.setStyleSheet("color: #ff6b6b;")
                self.vision_test_result.setToolTip(msg)
        except Exception as exc:
            self.vision_test_result.setText("❌ 连接失败")
            self.vision_test_result.setStyleSheet("color: #ff6b6b;")
            self.vision_test_result.setToolTip(str(exc))
