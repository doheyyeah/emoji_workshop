from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMovie, QPixmap
from PyQt6.QtWidgets import (
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
from services.replicate_service import ReplicateService, StickerGenerateWorker
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
        self.sticker_path = None
        self.sticker_worker = None
        self.sticker_movie = None

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
        self.prompt_counter.setObjectName("hintLabel")
        self.prompt_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        prompt_layout.addWidget(self.prompt_counter)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        settings_group = QGroupBox("生成设置")
        settings_layout = QFormLayout()

        self.apikey_edit = QLineEdit()
        self.apikey_edit.setEchoMode(QLineEdit.EchoMode.Password)
        settings_layout.addRow("API Key:", self.apikey_edit)

        self.base_url_edit = QLineEdit()
        settings_layout.addRow("Base URL:", self.base_url_edit)

        self.model_edit = QLineEdit()
        settings_layout.addRow("Model:", self.model_edit)

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
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.clicked.connect(self._browse_folder)
        save_layout.addWidget(self.save_edit)
        save_layout.addWidget(self.browse_btn)
        settings_layout.addRow("保存到:", save_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        btn_row = QHBoxLayout()
        self.generate_btn = QPushButton("🎨 开始生成")
        self.generate_btn.setObjectName("primaryButton")
        self.generate_btn.clicked.connect(self._start_generation)
        self.stop_btn = QPushButton("⏹ 停止生成")
        self.stop_btn.setObjectName("secondaryButton")
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
        self.preview_label.setObjectName("previewPane")
        self.preview_label.setProperty("hasImage", False)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        preview_layout.addWidget(self.preview_label)

        self.import_btn = QPushButton("➕ 导入到图片库")
        self.import_btn.setObjectName("primaryButton")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._import_generated)
        preview_layout.addWidget(self.import_btn)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

    def _setup_gif_tab(self):
        layout = QVBoxLayout(self.gif_tab)

        prompt_group = QGroupBox("描述动态贴纸")
        prompt_layout = QVBoxLayout()
        self.gif_prompt_edit = QTextEdit()
        self.gif_prompt_edit.setMaximumHeight(100)
        prompt_layout.addWidget(self.gif_prompt_edit)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        settings_group = QGroupBox("生成设置")
        settings_layout = QFormLayout()

        gif_save_layout = QHBoxLayout()
        self.gif_save_edit = QLineEdit()
        self.gif_save_edit.setReadOnly(True)
        self.gif_browse_btn = QPushButton("浏览...")
        self.gif_browse_btn.setObjectName("secondaryButton")
        self.gif_browse_btn.clicked.connect(self._browse_gif_folder)
        gif_save_layout.addWidget(self.gif_save_edit)
        gif_save_layout.addWidget(self.gif_browse_btn)
        settings_layout.addRow("保存到:", gif_save_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        self.gif_generate_btn = QPushButton("🎞 生成动图")
        self.gif_generate_btn.setObjectName("primaryButton")
        self.gif_generate_btn.clicked.connect(self._start_sticker_generation)
        layout.addWidget(self.gif_generate_btn)

        self.gif_status_label = QLabel("就绪")
        layout.addWidget(self.gif_status_label)

        preview_group = QGroupBox("GIF 预览")
        preview_layout = QVBoxLayout()

        self.gif_preview = QLabel("生成的 GIF 将在这里预览")
        self.gif_preview.setObjectName("previewPaneSmall")
        self.gif_preview.setProperty("hasImage", False)
        self.gif_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gif_preview.setMinimumHeight(220)
        preview_layout.addWidget(self.gif_preview)

        self.gif_save_btn = QPushButton("➕ 保存到库")
        self.gif_save_btn.setObjectName("primaryButton")
        self.gif_save_btn.setEnabled(False)
        self.gif_save_btn.clicked.connect(self._import_generated_sticker)
        preview_layout.addWidget(self.gif_save_btn)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
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

    def _browse_gif_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹")
        if folder:
            self.gif_save_edit.setText(folder)
            self.config.set("paths.last_export_folder", folder)

    def _load_settings(self):
        last_export_folder = self.config.get("paths.last_export_folder", str(Path.home() / "Desktop"))
        self.save_edit.setText(last_export_folder)
        self.gif_save_edit.setText(last_export_folder)

        cfg = self.config.get_ai_provider_config("custom")
        self.apikey_edit.setText(cfg.get("api_key", ""))
        self.base_url_edit.setText(cfg.get("base_url", ""))
        self.model_edit.setText(cfg.get("model", ""))

        self.apikey_edit.textChanged.connect(self._on_provider_field_changed)
        self.base_url_edit.textChanged.connect(self._on_provider_field_changed)
        self.model_edit.textChanged.connect(self._on_provider_field_changed)

    def _on_provider_field_changed(self):
        self.config.set_ai_provider_config(
            "custom",
            api_key=self.apikey_edit.text().strip(),
            model=self.model_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
            enabled=True,
        )
        self.config.set("ai_providers.active", "custom")

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
        provider = "custom"
        self._on_provider_field_changed()
        self.config.set("ai.provider", provider)
        self.config.set("ai_providers.active", provider)

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.generate_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.import_btn.setEnabled(False)
        self.preview_label.setText("生成中...")
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setProperty("hasImage", False)
        self.preview_label.style().unpolish(self.preview_label)
        self.preview_label.style().polish(self.preview_label)
        self.status_label.setText("正在连接 AI 并生成图片，请稍候…")

        self.worker = self.ai.generate_image(
            prompt=prompt,
            save_path=save_path,
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            provider=provider,
            api_key=self.apikey_edit.text().strip(),
            model=self.model_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
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
            self.preview_label.setProperty("hasImage", True)
            self.preview_label.style().unpolish(self.preview_label)
            self.preview_label.style().polish(self.preview_label)
        QMessageBox.information(self, "完成", "图片生成成功！")

    def _on_error(self, _error_msg: str):
        self._reset_generate_ui()
        self.status_label.setText("⚠️ AI 连接失败：网络不佳或 API Key 无效，请检查设置")
        self.preview_label.setText("生成失败")
        self.preview_label.setProperty("hasImage", False)
        self.preview_label.style().unpolish(self.preview_label)
        self.preview_label.style().polish(self.preview_label)
        QMessageBox.critical(self, "生成失败", "⚠️ AI 连接失败：网络不佳或 API Key 无效，请检查设置")

    def _start_sticker_generation(self):
        prompt = self.gif_prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入动图描述")
            return

        save_dir = self.gif_save_edit.text().strip()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请选择保存文件夹")
            return

        replicate_cfg = self.config.get_replicate_config()
        base_url = (replicate_cfg.get("base_url") or "").strip()
        api_key = (replicate_cfg.get("api_key") or "").strip()
        model = (replicate_cfg.get("model") or "fofr/sticker-maker").strip() or "fofr/sticker-maker"

        if not base_url or not api_key:
            QMessageBox.warning(
                self,
                "配置缺失",
                "请先到“设置 → 🤖 AI 推荐 → 🎬 动图生成”填写 Base URL 和 API Key，并测试连接。",
            )
            return

        import hashlib
        import time

        filename = f"sticker_{hashlib.md5(f'{prompt}:{time.time()}'.encode()).hexdigest()[:8]}.gif"
        output_path = str(Path(save_dir) / filename)

        service = ReplicateService(base_url=base_url, api_key=api_key, model=model)
        self.gif_generate_btn.setEnabled(False)
        self.gif_save_btn.setEnabled(False)
        self.gif_preview.setText("正在生成 GIF...")
        self.gif_preview.setToolTip("")
        self.gif_status_label.setText("正在提交任务…")

        self.sticker_worker = StickerGenerateWorker(
            service=service,
            prompt=prompt,
            output_path=output_path,
            timeout=300,
            parent=self,
        )
        self.sticker_worker.progress.connect(self._on_sticker_progress)
        self.sticker_worker.finished.connect(self._on_sticker_finished)
        self.sticker_worker.error.connect(self._on_sticker_error)
        self.sticker_worker.finished.connect(lambda _: self._on_sticker_done())
        self.sticker_worker.error.connect(lambda _: self._on_sticker_done())
        self.sticker_worker.start()

    def _on_sticker_progress(self, message: str):
        self.gif_status_label.setText(message)

    def _on_sticker_finished(self, gif_path: str):
        self.sticker_path = gif_path
        self.gif_status_label.setText("动图生成成功")
        self.gif_save_btn.setEnabled(True)

        if self.sticker_movie:
            self.sticker_movie.stop()
            self.sticker_movie = None
        self.sticker_movie = QMovie(gif_path)
        if self.sticker_movie.isValid():
            self.gif_preview.setMovie(self.sticker_movie)
            self.gif_preview.setProperty("hasImage", True)
            self.gif_preview.style().unpolish(self.gif_preview)
            self.gif_preview.style().polish(self.gif_preview)
            self.sticker_movie.start()
        else:
            pixmap = QPixmap(gif_path)
            self.gif_preview.setPixmap(pixmap)
            self.gif_preview.setProperty("hasImage", True)
            self.gif_preview.style().unpolish(self.gif_preview)
            self.gif_preview.style().polish(self.gif_preview)

        QMessageBox.information(self, "完成", "动图生成成功！")

    def _on_sticker_error(self, message: str):
        self.gif_status_label.setText("生成失败")
        self.gif_preview.setText("生成失败")
        self.gif_preview.setProperty("hasImage", False)
        self.gif_preview.style().unpolish(self.gif_preview)
        self.gif_preview.style().polish(self.gif_preview)
        self.gif_preview.setToolTip(message)
        QMessageBox.critical(self, "生成失败", message)

    def _on_sticker_done(self):
        self.gif_generate_btn.setEnabled(True)
        self.sticker_worker = None

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

    def _import_generated_sticker(self):
        if not self.sticker_path or not Path(self.sticker_path).exists():
            QMessageBox.warning(self, "错误", "没有可导入的 GIF")
            return
        info = FileScanner.get_image_info(self.sticker_path)
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

        if self.sticker_worker and self.sticker_worker.isRunning():
            QMessageBox.warning(self, "提示", "动图正在生成中，请稍候完成后再关闭窗口")
            event.ignore()
            return

        event.accept()
