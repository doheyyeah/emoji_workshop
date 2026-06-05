from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QColorDialog,
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
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.ai_service import AIService
from services.database_service import DatabaseService
from services.gif_generator import GifGenerator, AnimationMode, ANIMATION_MODE_NAMES
from utils.config_manager import ConfigManager
from utils.file_scanner import FileScanner


class MultiFrameGifWorker(QThread):
    """后台生成多帧 GIF，避免阻塞主线程"""

    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        ai_service: AIService,
        prompt: str,
        save_dir: str,
        output_path: str,
        frame_count: int,
        duration: int,
        provider: str,
        width: int,
        height: int,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.ai_service = ai_service
        self.prompt = prompt
        self.save_dir = save_dir
        self.output_path = output_path
        self.frame_count = frame_count
        self.duration = duration
        self.provider = provider
        self.width = width
        self.height = height
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def run(self):
        try:
            provider_obj = self.ai_service.providers.get(self.provider, self.ai_service.providers["pollinations"])
            temp_paths = []
            for i in range(self.frame_count):
                if self.isInterruptionRequested():
                    return
                self.progress.emit(f"正在连接 AI 并生成第 {i + 1}/{self.frame_count} 帧…")
                path = str(Path(self.save_dir) / f"gif_frame_{i}.png")
                image_bytes = provider_obj.generate(
                    self.prompt,
                    self.width,
                    self.height,
                    api_key=self.api_key,
                    model=self.model,
                    base_url=self.base_url,
                )
                with open(path, "wb") as f:
                    f.write(image_bytes)
                temp_paths.append(path)
            output = GifGenerator.make_multiframe_gif(temp_paths, self.output_path, duration=self.duration)
            self.finished.emit(output)
        except Exception:
            self.error.emit("⚠️ AI 连接失败：网络不佳或 API Key 无效，请检查设置")


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
        self.gif_path_b = None
        self.gif_worker = None

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
        self.prompt_counter.setObjectName("promptCounter")
        self.prompt_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        prompt_layout.addWidget(self.prompt_counter)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        settings_group = QGroupBox("生成设置")
        settings_layout = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_display_map = {
            "doubao": "豆包 Seedream 5.0 Lite",
            "pollinations": "Pollinations (免费)",
            "custom": "🛠 自定义",
        }
        settings_layout.addRow("AI 提供商:", self.provider_combo)

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
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setObjectName("previewPane")
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

        # 使用子标签页区分模式 A 和模式 B
        self.gif_sub_tabs = QTabWidget()
        layout.addWidget(self.gif_sub_tabs)

        # === 模式 A：静图 + 文字动画 ===
        mode_a_tab = QWidget()
        a_layout = QVBoxLayout(mode_a_tab)

        a_group = QGroupBox("背景图与文字")
        a_form = QFormLayout()

        # 选择背景图
        self.gif_base_edit = QLineEdit()
        self.gif_base_edit.setPlaceholderText("选择背景图片...")
        base_btn = QPushButton("浏览...")
        base_btn.clicked.connect(self._browse_base_image)
        base_layout = QHBoxLayout()
        base_layout.addWidget(self.gif_base_edit)
        base_layout.addWidget(base_btn)
        a_form.addRow("背景图:", base_layout)

        # 叠加文字
        self.gif_text_edit = QLineEdit()
        self.gif_text_edit.setMaxLength(20)
        self.gif_text_edit.setPlaceholderText("输入文字（最多 20 字）")
        a_form.addRow("叠加文字:", self.gif_text_edit)

        # 动画方式
        self.anim_mode_combo = QComboBox()
        self.anim_mode_combo.addItems(ANIMATION_MODE_NAMES)
        a_form.addRow("动画方式:", self.anim_mode_combo)

        # 字体大小
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(20, 60)
        self.font_size_slider.setValue(36)
        self.font_size_label = QLabel("36")
        self.font_size_slider.valueChanged.connect(
            lambda v: self.font_size_label.setText(str(v))
        )
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_label)
        a_form.addRow("字体大小:", font_size_layout)

        # 文字颜色
        self._gif_text_color = "#FFE600"
        self.color_btn = QPushButton("选择颜色")
        self.color_btn.setObjectName("colorButton")
        self.color_btn.setStyleSheet(f"background-color: {self._gif_text_color};")
        self.color_btn.clicked.connect(self._pick_text_color)
        a_form.addRow("文字颜色:", self.color_btn)

        a_group.setLayout(a_form)
        a_layout.addWidget(a_group)

        self.gif_generate_btn = QPushButton("🎞 生成动图")
        self.gif_generate_btn.setObjectName("primaryButton")
        self.gif_generate_btn.clicked.connect(self._generate_gif_mode_a)
        a_layout.addWidget(self.gif_generate_btn)

        self.gif_preview = QLabel("GIF 预览")
        self.gif_preview.setObjectName("previewPaneSmall")
        self.gif_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gif_preview.setMinimumHeight(200)
        a_layout.addWidget(self.gif_preview)

        self.gif_save_btn = QPushButton("➕ 保存到库")
        self.gif_save_btn.setObjectName("primaryButton")
        self.gif_save_btn.setEnabled(False)
        self.gif_save_btn.clicked.connect(self._import_generated_gif)
        a_layout.addWidget(self.gif_save_btn)
        a_layout.addStretch()

        self.gif_sub_tabs.addTab(mode_a_tab, "静图+文字动画")

        # === 模式 B：多帧 AI 拼接 ===
        mode_b_tab = QWidget()
        b_layout = QVBoxLayout(mode_b_tab)

        warn_label = QLabel(
            "⚠️ 此模式需要调用 AI API 多次，耗时约 30 秒，效果可能不稳定"
        )
        warn_label.setWordWrap(True)
        warn_label.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 4px;")
        b_layout.addWidget(warn_label)

        b_form = QFormLayout()

        # 帧数
        self.gif_frames_spin = QSpinBox()
        self.gif_frames_spin.setRange(3, 5)
        self.gif_frames_spin.setValue(4)
        b_form.addRow("帧数:", self.gif_frames_spin)

        # 帧间隔
        self.gif_duration_spin = QSpinBox()
        self.gif_duration_spin.setRange(150, 500)
        self.gif_duration_spin.setSingleStep(50)
        self.gif_duration_spin.setValue(200)
        self.gif_duration_spin.setSuffix(" ms")
        b_form.addRow("帧间隔:", self.gif_duration_spin)

        b_layout.addLayout(b_form)

        self.gif_b_generate_btn = QPushButton("🎞 生成多帧 GIF")
        self.gif_b_generate_btn.setObjectName("primaryButton")
        self.gif_b_generate_btn.clicked.connect(self._generate_gif_mode_b)
        b_layout.addWidget(self.gif_b_generate_btn)

        self.gif_b_preview = QLabel("GIF 预览")
        self.gif_b_preview.setObjectName("previewPaneSmall")
        self.gif_b_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gif_b_preview.setMinimumHeight(200)
        b_layout.addWidget(self.gif_b_preview)

        self.gif_b_save_btn = QPushButton("➕ 保存到库")
        self.gif_b_save_btn.setObjectName("primaryButton")
        self.gif_b_save_btn.setEnabled(False)
        self.gif_b_save_btn.clicked.connect(self._import_generated_gif_b)
        b_layout.addWidget(self.gif_b_save_btn)
        b_layout.addStretch()

        self.gif_sub_tabs.addTab(mode_b_tab, "多帧 AI 拼接")

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
        preferred = self.config.get("ai_providers.active", self.config.get("ai.provider", "doubao"))
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == preferred:
                self.provider_combo.setCurrentIndex(i)
                break
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.apikey_edit.textChanged.connect(self._on_provider_field_changed)
        self.base_url_edit.textChanged.connect(self._on_provider_field_changed)
        self.model_edit.textChanged.connect(self._on_provider_field_changed)
        self._on_provider_changed()

    def _current_provider(self) -> str:
        return self.provider_combo.currentData() or "pollinations"

    def _on_provider_changed(self):
        provider = self._current_provider()
        cfg = self.config.get_ai_provider_config(provider)
        self.apikey_edit.blockSignals(True)
        self.base_url_edit.blockSignals(True)
        self.model_edit.blockSignals(True)
        self.apikey_edit.setText(cfg.get("api_key", ""))
        self.base_url_edit.setText(cfg.get("base_url", ""))
        self.model_edit.setText(cfg.get("model", ""))
        self.apikey_edit.blockSignals(False)
        self.base_url_edit.blockSignals(False)
        self.model_edit.blockSignals(False)

        is_pollinations = provider == "pollinations"
        self.apikey_edit.setEnabled(not is_pollinations)
        self.model_edit.setEnabled(not is_pollinations)
        self.base_url_edit.setEnabled(provider == "custom")
        if is_pollinations:
            self.apikey_edit.setPlaceholderText("免费,无需 Key")
        elif provider == "doubao":
            self.apikey_edit.setPlaceholderText("请输入豆包 API Key")
        else:
            self.apikey_edit.setPlaceholderText("请输入 API Key")

    def _on_provider_field_changed(self):
        provider = self._current_provider()
        self.config.set_ai_provider_config(
            provider,
            api_key=self.apikey_edit.text().strip(),
            model=self.model_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
            enabled=True,
        )
        self.config.set("ai_providers.active", provider)

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
        if provider != "pollinations":
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
            try:
                self.preview_label.style().unpolish(self.preview_label)
                self.preview_label.style().polish(self.preview_label)
            except Exception:
                pass
            self.preview_label.update()
        QMessageBox.information(self, "完成", "图片生成成功！")

    def _on_error(self, _error_msg: str):
        self._reset_generate_ui()
        self.status_label.setText("⚠️ AI 连接失败：网络不佳或 API Key 无效，请检查设置")
        self.preview_label.setText("生成失败")
        QMessageBox.critical(self, "生成失败", "⚠️ AI 连接失败：网络不佳或 API Key 无效，请检查设置")

    def _pick_text_color(self):
        from PyQt6.QtGui import QColor
        color = QColorDialog.getColor(QColor(self._gif_text_color), self, "选择文字颜色")
        if color.isValid():
            self._gif_text_color = color.name()
            self.color_btn.setStyleSheet(f"background-color: {self._gif_text_color};")

    def _generate_gif_mode_a(self):
        """模式 A：静图 + 文字动画"""
        base = self.gif_base_edit.text().strip()
        if not base:
            QMessageBox.warning(self, "提示", "请先选择背景图片")
            return
        text = self.gif_text_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入叠加文字")
            return
        save_dir = self.save_edit.text().strip() or str(Path.home() / "Desktop")
        output_path = str(Path(save_dir) / "animated_emoji.gif")
        mode_name = self.anim_mode_combo.currentText()
        font_size = self.font_size_slider.value()
        try:
            self.gif_path = GifGenerator.make_text_animated_gif(
                base_image_path=base,
                text=text,
                output_path=output_path,
                mode=mode_name,
                font_size=font_size,
                text_color=self._gif_text_color,
            )
            self.gif_preview.setPixmap(QPixmap(self.gif_path))
            self.gif_preview.setStyleSheet("QLabel { border: none; }")
            self.gif_save_btn.setEnabled(True)
            QMessageBox.information(self, "完成", "动图生成成功！")
        except Exception as exc:
            QMessageBox.critical(self, "生成失败", "生成失败,请检查 API Key 或更换提供商")
            self.gif_preview.setToolTip(str(exc))

    def _generate_gif_mode_b(self):
        """模式 B：多帧 AI 拼接"""
        prompt = self.prompt_edit.toPlainText().strip() or "funny emoji"
        save_dir = self.save_edit.text().strip() or str(Path.home() / "Desktop")
        output_path = str(Path(save_dir) / "multiframe_emoji.gif")
        frame_count = self.gif_frames_spin.value()
        duration = self.gif_duration_spin.value()
        provider = self.provider_combo.currentData()
        if provider != "pollinations":
            self._on_provider_field_changed()

        self.gif_b_generate_btn.setEnabled(False)
        self.gif_b_save_btn.setEnabled(False)
        self.gif_b_preview.setText("正在连接 AI 并生成多帧 GIF…")
        self.status_label.setText("正在连接 AI 并生成多帧 GIF，请稍候…")

        self.gif_worker = MultiFrameGifWorker(
            ai_service=self.ai,
            prompt=prompt,
            save_dir=save_dir,
            output_path=output_path,
            frame_count=frame_count,
            duration=duration,
            provider=provider,
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            api_key=self.apikey_edit.text().strip(),
            model=self.model_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
            parent=self,
        )
        self.gif_worker.progress.connect(self.status_label.setText)
        self.gif_worker.finished.connect(self._on_gif_b_finished)
        self.gif_worker.error.connect(self._on_gif_b_error)
        self.gif_worker.finished.connect(lambda _: self._on_gif_b_done())
        self.gif_worker.error.connect(lambda _: self._on_gif_b_done())
        self.gif_worker.start()

    def _on_gif_b_finished(self, gif_path: str):
        self.gif_path_b = gif_path
        self.gif_b_preview.setPixmap(QPixmap(gif_path))
        self.gif_b_preview.setProperty("hasImage", True)
        try:
            self.gif_b_preview.style().unpolish(self.gif_b_preview)
            self.gif_b_preview.style().polish(self.gif_b_preview)
        except Exception:
            pass
        self.gif_b_preview.update()
        self.gif_b_save_btn.setEnabled(True)
        self.status_label.setText("多帧 GIF 生成成功")
        QMessageBox.information(self, "完成", "多帧 GIF 生成成功！")

    def _on_gif_b_error(self, msg: str):
        self.gif_b_preview.setText("生成失败")
        self.status_label.setText(msg)
        QMessageBox.critical(self, "生成失败", msg)

    def _on_gif_b_done(self):
        self.gif_b_generate_btn.setEnabled(True)
        self.gif_worker = None

    def _generate_gif(self):
        """兼容旧接口（自动路由到模式 A）"""
        self._generate_gif_mode_a()

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

    def _import_generated_gif_b(self):
        if not self.gif_path_b or not Path(self.gif_path_b).exists():
            QMessageBox.warning(self, "错误", "没有可导入的 GIF")
            return
        info = FileScanner.get_image_info(self.gif_path_b)
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
