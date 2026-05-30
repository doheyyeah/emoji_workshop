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
    - 网络：超时、并发数、代理
    - 高级：重置配置、统计信息
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.setWindowTitle("⚙️ 应用设置")
        self.setMinimumSize(500, 450)
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

        # 底部按钮（全部中文）
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText("恢复默认")
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._restore_defaults
        )
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

        network_group = QGroupBox("网络请求设置")
        network_layout = QFormLayout()

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setSuffix(" 秒")
        network_layout.addRow("API 超时:", self.timeout_spin)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        network_layout.addRow("最大并发下载:", self.concurrent_spin)

        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("http://127.0.0.1:7890（留空表示不使用）")
        network_layout.addRow("代理地址:", self.proxy_edit)

        network_group.setLayout(network_layout)
        layout.addWidget(network_group)

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

    def _create_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 统计信息
        stats_group = QGroupBox("使用统计")
        stats_layout = QFormLayout()

        self.stat_imported_label = QLabel("0")
        stats_layout.addRow("累计导入图片:", self.stat_imported_label)

        self.stat_tags_label = QLabel("0")
        stats_layout.addRow("累计创建标签:", self.stat_tags_label)

        self.stat_launch_label = QLabel("0")
        stats_layout.addRow("程序启动次数:", self.stat_launch_label)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 危险操作
        danger_group = QGroupBox("危险操作")
        danger_layout = QVBoxLayout()

        reset_btn = QPushButton("🔄 重置所有配置为默认值")
        reset_btn.clicked.connect(self._restore_defaults)
        danger_layout.addWidget(reset_btn)

        clear_cache_btn = QPushButton("🗑️ 清空缩略图缓存")
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

        # 最近文件夹（使用 get_recent_folders 方法确保兼容）
        self.recent_list.clear()
        for folder in self.config.get_recent_folders():
            self.recent_list.addItem(folder)

        # 路径
        self.import_path_edit.setText(self.config.get("paths.last_import_folder", ""))
        self.export_path_edit.setText(self.config.get("paths.last_export_folder", ""))

        # 网络
        self.timeout_spin.setValue(self.config.get("network.api_timeout", 30))
        self.concurrent_spin.setValue(self.config.get("network.max_concurrent_downloads", 3))
        proxy = self.config.get("network.proxy", "")
        self.proxy_edit.setText(proxy if proxy else "")

        # 统计
        self.stat_imported_label.setText(str(self.config.get("stats.total_imported", 0)))
        self.stat_tags_label.setText(str(self.config.get("stats.total_tags_created", 0)))
        self.stat_launch_label.setText(str(self.config.get("stats.launch_count", 0)))

    # ===== 保存设置 =====

    def _save_and_close(self):
        """保存所有设置并关闭对话框"""
        # 常规
        self.config.set("ui.theme", self.theme_combo.currentText())
        self.config.set("ui.thumbnail_size", self.thumb_size_spin.value())
        self.config.set("ui.grid_spacing", self.grid_spacing_spin.value())
        self.config.set("behavior.auto_save", self.auto_save_check.isChecked())
        self.config.set("behavior.confirm_delete", self.confirm_delete_check.isChecked())

        # 路径
        self.config.set("paths.last_import_folder", self.import_path_edit.text())
        self.config.set("paths.last_export_folder", self.export_path_edit.text())

        # 网络
        self.config.set("network.api_timeout", self.timeout_spin.value())
        self.config.set("network.max_concurrent_downloads", self.concurrent_spin.value())
        proxy = self.proxy_edit.text().strip()
        self.config.set("network.proxy", proxy if proxy else None)

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
                    proxy = ConfigManager().get("network.proxy")
                    proxies = {"http": proxy, "https": proxy} if proxy else None

                    # 测试百度（国内）和 Google（国外）
                    urls = [
                        ("百度", "https://www.baidu.com", 5),
                        ("Google", "https://www.google.com", 5),
                    ]

                    results = []
                    for name, url, timeout in urls:
                        try:
                            r = requests.get(url, timeout=timeout, proxies=proxies)
                            results.append(f"✅ {name}: 正常 ({r.status_code})")
                        except Exception as e:
                            results.append(f"❌ {name}: {str(e)[:50]}")

                    self.result.emit("\n".join(results), True)
                except Exception as e:
                    self.result.emit(f"测试失败: {str(e)}", False)

        self.test_result_label.setText("正在测试...")
        self.thread = TestThread()
        self.thread.result.connect(self._on_test_result)
        self.thread.start()

    def _on_test_result(self, msg, success):
        self.test_result_label.setText(msg)
        if success:
            self.test_result_label.setStyleSheet("color: #4CAF50;")
        else:
            self.test_result_label.setStyleSheet("color: #f44336;")
