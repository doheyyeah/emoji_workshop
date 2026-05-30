from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.ai_service import AIService
from services.database_service import DatabaseService
from services.gif_generator import GifGenerator
from utils.config_manager import ConfigManager
from utils.file_scanner import FileScanner


class AIGenerateDialog(QDialog):
    """AI 文生图与 GIF 生成对话框"""

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.ai = AIService()
        self.config = ConfigManager()
        self.worker = None
        self.generated_path = None
        self.gif_path = None

        self.setWindowTitle("🎨 AI 生成表情包")
        self.setMinimumSize(650, 760)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.image_tab = QWidget()
        self.gif_tab = QWidget()
        self.tabs.addTab(self.image_tab, "🖼 生成静图")
        self.tabs.addTab(self.gif_tab, "🎞 生成动图")
        layout.addWidget(self.tabs)

        self._setup_image_tab()
        self._setup_gif_tab()

    def _setup_image_tab(self):
        layout = QVBoxLayout(self.image_tab)
        prompt_group = QGroupBox("描述你的表情包")
        prompt_layout = QVBoxLayout()
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(100)
        self.prompt_edit.textChanged.connect(self._on_prompt_changed)
        prompt_layout.addWidget(self.prompt_edit)
        self.prompt_counter = QLabel("0/200")
        self.prompt_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.prompt_counter.setStyleSheet("color:#aaa;font-size:11px;")
        prompt_layout.addWidget(self.prompt_counter)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        settings_group = QGroupBox("生成设置")
        settings_layout = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_display_map = {
            "doubao": "豆包 (火山引擎)",
            "pollinations": "Pollinations (免费)",
        }
        settings_layout.addRow("AI 提供商:", self.provider_combo)

        self.apikey_edit = QLineEdit()
        self.apikey_edit.setEchoMode(QLineEdit.EchoMode.Password)
        settings_layout.addRow("API Key:", self.apikey_edit)

        size_layout = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(256, 1024)
        self.width_spin.setSingleStep(64)
        self.width_spin.setValue(512)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(256, 1024)
        self.height_spin.setSingleStep(64)
        self.height_spin.setValue(512)
        size_layout.addWidget(QLabel("宽:"))
        size_layout.addWidget(self.width_spin)
        size_layout.addWidget(QLabel("高:"))
        size_layout.addWidget(self.height_spin)
        settings_layout.addRow("图片尺寸:", size_layout)

        save_layout = QHBoxLayout()
        self.save_edit = QLineEdit()
        self.save_edit.setReadOnly(True)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._browse_folder)
        save_layout.addWidget(self.save_edit)
        save_layout.addWidget(self.browse_btn)
        settings_layout.addRow("保存到:", save_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        btn_row = QHBoxLayout()
        self.generate_btn = QPushButton("🎨 开始生成")
        self.generate_btn.clicked.connect(self._start_generation)
        self.stop_btn = QPushButton("⏹ 停止生成")
        self.stop_btn.clicked.connect(self._stop_generation)
        self.stop_btn.setVisible(False)
        btn_row.addWidget(self.generate_btn)
        btn_row.addWidget(self.stop_btn)
        layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        preview_group = QGroupBox("预览")
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel("生成的图片将在这里预览")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("QLabel { background-color: #2d2d2d; color: #888; border: 2px dashed #555; border-radius: 8px; }")
        preview_layout.addWidget(self.preview_label)

        self.import_btn = QPushButton("➕ 导入到图片库")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._import_generated)
        preview_layout.addWidget(self.import_btn)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

    def _setup_gif_tab(self):
        layout = QVBoxLayout(self.gif_tab)
        mode_group = QGroupBox("动图模式")
        mode_form = QFormLayout()
        self.gif_mode_combo = QComboBox()
        self.gif_mode_combo.addItems(["静图+文字动画", "多帧 AI 拼接"])
        mode_form.addRow("模式:", self.gif_mode_combo)
        self.gif_base_edit = QLineEdit()
        base_btn = QPushButton("选择图片")
        base_btn.clicked.connect(self._browse_base_image)
        base_layout = QHBoxLayout()
        base_layout.addWidget(self.gif_base_edit)
        base_layout.addWidget(base_btn)
        mode_form.addRow("基础图片:", base_layout)
        self.gif_text_edit = QLineEdit()
        self.gif_text_edit.setPlaceholderText("输入动图文字")
        mode_form.addRow("叠加文字:", self.gif_text_edit)
        mode_group.setLayout(mode_form)
        layout.addWidget(mode_group)

        self.gif_generate_btn = QPushButton("🎞 生成动图")
        self.gif_generate_btn.clicked.connect(self._generate_gif)
        layout.addWidget(self.gif_generate_btn)

        self.gif_preview = QLabel("GIF 预览")
        self.gif_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gif_preview.setMinimumHeight(240)
        self.gif_preview.setStyleSheet("QLabel { background-color: #2d2d2d; color: #888; border: 2px dashed #555; border-radius: 8px; }")
        layout.addWidget(self.gif_preview)

        self.gif_save_btn = QPushButton("➕ 保存到库")
        self.gif_save_btn.setEnabled(False)
        self.gif_save_btn.clicked.connect(self._import_generated_gif)
        layout.addWidget(self.gif_save_btn)
        layout.addStretch()

    def _on_prompt_changed(self):
        text = self.prompt_edit.toPlainText()
        if len(text) > 200:
            cursor = self.prompt_edit.textCursor()
            pos = cursor.position()
            self.prompt_edit.blockSignals(True)
            self.prompt_edit.setPlainText(text[:200])
            self.prompt_edit.blockSignals(False)
            cursor.setPosition(min(pos, 200))
            self.prompt_edit.setTextCursor(cursor)
            text = self.prompt_edit.toPlainText()
        self.prompt_counter.setText(f"{len(text)}/200")

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹")
        if folder:
            self.save_edit.setText(folder)
            self.config.set("paths.last_export_folder", folder)

    def _browse_base_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择基础图片", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if path:
            self.gif_base_edit.setText(path)

    def _load_settings(self):
        self.save_edit.setText(self.config.get("paths.last_export_folder", str(Path.home() / "Desktop")))
        enabled_keys = self.ai.get_enabled_providers()
        self.provider_combo.clear()
        for key in enabled_keys:
            self.provider_combo.addItem(self.provider_display_map.get(key, key), userData=key)
        preferred = self.config.get("ai.provider", "doubao")
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == preferred:
                self.provider_combo.setCurrentIndex(i)
                break
        self.apikey_edit.setText(self.config.get("ai.doubao_api_key", ""))

    def _start_generation(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入图片描述")
            return
        save_dir = self.save_edit.text().strip()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请选择保存文件夹")
            return

        import hashlib
        import time
        filename = f"ai_{hashlib.md5(f'{prompt}:{time.time()}'.encode()).hexdigest()[:8]}.png"
        save_path = str(Path(save_dir) / filename)
        provider = self.provider_combo.currentData()
        if provider == "doubao":
            self.config.set("ai.doubao_api_key", self.apikey_edit.text().strip())
        self.config.set("ai.provider", provider)

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.generate_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.import_btn.setEnabled(False)
        self.preview_label.setText("生成中...")
        self.preview_label.setPixmap(QPixmap())
        self.status_label.setText("正在生成图片，请稍候...")

        self.worker = self.ai.generate_image(
            prompt=prompt,
            save_path=save_path,
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            provider=provider,
            progress_callback=self._on_progress,
            finished_callback=self._on_finished,
            error_callback=self._on_error,
        )

    def _stop_generation(self):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(1000)
        self._reset_generate_ui()
        self.status_label.setText("已停止生成")

    def _reset_generate_ui(self):
        self.progress.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.stop_btn.setVisible(False)

    def _on_progress(self, msg: str):
        self.status_label.setText(msg)

    def _on_finished(self, save_path: str):
        self.generated_path = save_path
        self._reset_generate_ui()
        self.import_btn.setEnabled(True)
        self.status_label.setText("生成成功")
        pixmap = QPixmap(save_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.preview_label.width() - 20,
                self.preview_label.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
            self.preview_label.setStyleSheet("QLabel { border: none; }")
        QMessageBox.information(self, "完成", "图片生成成功！")

    def _on_error(self, _error_msg: str):
        self._reset_generate_ui()
        self.status_label.setText("生成失败,请检查 API Key 或更换提供商")
        self.preview_label.setText("生成失败")
        QMessageBox.critical(self, "生成失败", "生成失败,请检查 API Key 或更换提供商")

    def _generate_gif(self):
        save_dir = self.save_edit.text().strip() or str(Path.home() / "Desktop")
        output_path = str(Path(save_dir) / "generated_emoji.gif")
        mode = self.gif_mode_combo.currentText()
        try:
            if mode == "静图+文字动画":
                base = self.gif_base_edit.text().strip()
                if not base:
                    QMessageBox.warning(self, "提示", "请先选择基础图片")
                    return
                text = self.gif_text_edit.text().strip() or "哈哈哈"
                self.gif_path = GifGenerator.make_text_animated_gif(base, text, output_path)
            else:
                prompt = self.prompt_edit.toPlainText().strip() or "funny emoji"
                temp_paths = []
                for i in range(4):
                    path = str(Path(save_dir) / f"gif_frame_{i}.png")
                    self.ai.generate_image(
                        prompt=prompt,
                        save_path=path,
                        provider=self.provider_combo.currentData(),
                    ).wait(120000)
                    temp_paths.append(path)
                self.gif_path = GifGenerator.make_multiframe_gif(temp_paths, output_path)

            self.gif_preview.setPixmap(QPixmap(self.gif_path))
            self.gif_preview.setStyleSheet("QLabel { border: none; }")
            self.gif_save_btn.setEnabled(True)
        except Exception as exc:
            QMessageBox.critical(self, "生成失败", "生成失败,请检查 API Key 或更换提供商")
            self.status_label.setToolTip(str(exc))

    def _import_generated(self):
        if not self.generated_path or not Path(self.generated_path).exists():
            QMessageBox.warning(self, "错误", "没有可导入的图片")
            return
        info = FileScanner.get_image_info(self.generated_path)
        if info:
            info["name"] = f"AI_{info['name'][:20]}"
            image_id = self.db.add_image(**info)
            if image_id:
                self.config.increment_stat("total_imported")
                QMessageBox.information(self, "成功", f"已导入到图片库 (ID: {image_id})")
            else:
                QMessageBox.warning(self, "提示", "导入失败，可能已存在")

    def _import_generated_gif(self):
        if not self.gif_path or not Path(self.gif_path).exists():
            QMessageBox.warning(self, "错误", "没有可导入的 GIF")
            return
        info = FileScanner.get_image_info(self.gif_path)
        if info:
            self.db.add_image(**info)
            QMessageBox.information(self, "成功", "GIF 已保存到库")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认",
                "生成正在进行中，确定要取消吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.requestInterruption()
                self.worker.wait(2000)
            else:
                event.ignore()
                return
        event.accept()
