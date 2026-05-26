from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QComboBox, QSpinBox, QTextEdit,
    QFileDialog, QMessageBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from pathlib import Path

from services.ai_service import AIService
from services.database_service import DatabaseService
from utils.config_manager import ConfigManager
from utils.file_scanner import FileScanner


class AIGenerateDialog(QDialog):
    """AI 文生图对话框

    功能：
    - 输入文字描述生成表情包
    - 选择提供商（Pollinations 免费 / 硅基流动）
    - 设置图片尺寸
    - 预览生成的图片
    - 一键导入到图片库
    """

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.ai = AIService()
        self.config = ConfigManager()
        self.worker = None
        self.generated_path = None

        self.setWindowTitle("🎨 AI 生成表情包")
        self.setMinimumSize(600, 700)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # === 提示词输入 ===
        prompt_group = QGroupBox("描述你的表情包")
        prompt_layout = QVBoxLayout()

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            "例如：\n"
            "- a cute cat with big eyes, cartoon style\n"
            "- 一只开心的柴犬，简笔画风格\n"
            "- funny programmer meme, pixel art"
        )
        self.prompt_edit.setMaximumHeight(100)
        prompt_layout.addWidget(self.prompt_edit)

        # 快捷提示
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("快捷提示:"))

        quick_prompts = [
            "可爱猫咪", "开心狗狗", "搞笑熊猫",
            "程序员梗", "庆祝表情", "无奈摊手"
        ]
        for text in quick_prompts:
            btn = QPushButton(text)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, t=text: self._set_quick_prompt(t))
            quick_layout.addWidget(btn)

        prompt_layout.addLayout(quick_layout)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        # === 设置 ===
        settings_group = QGroupBox("生成设置")
        settings_layout = QFormLayout()

        # 提供商选择
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Pollinations.ai（免费）", "硅基流动（需API Key）"])
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        settings_layout.addRow("AI 提供商:", self.provider_combo)

        # API Key（硅基流动需要）
        self.apikey_edit = QLineEdit()
        self.apikey_edit.setPlaceholderText("sk-xxxxxxxx（仅硅基流动需要）")
        self.apikey_edit.setEchoMode(QLineEdit.EchoMode.Password)
        settings_layout.addRow("API Key:", self.apikey_edit)

        # 尺寸
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
        size_layout.addStretch()

        settings_layout.addRow("图片尺寸:", size_layout)

        # 保存路径
        save_layout = QHBoxLayout()
        self.save_edit = QLineEdit()
        self.save_edit.setReadOnly(True)
        save_layout.addWidget(self.save_edit)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._browse_folder)
        save_layout.addWidget(self.browse_btn)

        settings_layout.addRow("保存到:", save_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # === 生成按钮 ===
        self.generate_btn = QPushButton("🎨 开始生成")
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #7B1FA2; }
            QPushButton:disabled { background-color: #666; }
        """)
        self.generate_btn.clicked.connect(self._start_generation)
        layout.addWidget(self.generate_btn)

        # === 进度 ===
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        # === 预览区域 ===
        preview_group = QGroupBox("预览")
        preview_layout = QVBoxLayout()

        self.preview_label = QLabel("生成的图片将在这里预览")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                color: #888;
                border: 2px dashed #555;
                border-radius: 8px;
            }
        """)
        preview_layout.addWidget(self.preview_label)

        # 导入按钮
        self.import_btn = QPushButton("➕ 导入到图片库")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._import_generated)
        preview_layout.addWidget(self.import_btn)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

    def _set_quick_prompt(self, text: str):
        """设置快捷提示词"""
        prompts = {
            "可爱猫咪": "a cute cat with big eyes, kawaii style, emoji",
            "开心狗狗": "a happy shiba inu dog, smiling, cartoon style",
            "搞笑熊猫": "a funny panda doing silly face, meme style",
            "程序员梗": "a programmer debugging at 3am, funny meme, pixel art",
            "庆祝表情": "celebration emoji, confetti, colorful, cute",
            "无奈摊手": "shrugging person, confused, comic style"
        }
        self.prompt_edit.setPlainText(prompts.get(text, text))

    def _on_provider_changed(self, index: int):
        """切换提供商时更新 UI"""
        is_siliconflow = (index == 1)
        self.apikey_edit.setEnabled(is_siliconflow)
        if not is_siliconflow:
            self.apikey_edit.clear()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹")
        if folder:
            self.save_edit.setText(folder)
            self.config.set("paths.last_export_folder", folder)

    def _load_settings(self):
        """加载保存的设置"""
        self.save_edit.setText(
            self.config.get("paths.last_export_folder", 
                           str(Path.home() / "Desktop"))
        )

        # 加载 API Key（如果有）
        api_key = self.config.get("ai.siliconflow_api_key", "")
        if api_key:
            self.apikey_edit.setText(api_key)

    def _start_generation(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入图片描述")
            return

        save_dir = self.save_edit.text()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请选择保存文件夹")
            return

        # 生成文件名
        import hashlib
        import time
        hash_input = f"{prompt}:{time.time()}"
        filename = f"ai_{hashlib.md5(hash_input.encode()).hexdigest()[:8]}.png"
        save_path = f"{save_dir}/{filename}"

        # 确定提供商
        provider = "pollinations" if self.provider_combo.currentIndex() == 0 else "siliconflow"

        # 保存 API Key 到配置
        if provider == "siliconflow":
            api_key = self.apikey_edit.text().strip()
            if not api_key:
                QMessageBox.warning(self, "提示", "硅基流动需要提供 API Key")
                return
            self.config.set("ai.siliconflow_api_key", api_key)
            self.config.set("ai.provider", "siliconflow")
        else:
            self.config.set("ai.provider", "pollinations")

        # 更新 UI
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度
        self.generate_btn.setEnabled(False)
        self.import_btn.setEnabled(False)
        self.preview_label.setText("生成中...")
        self.preview_label.setPixmap(QPixmap())
        self.status_label.setText("正在生成图片，请稍候...")

        # 开始生成
        self.worker = self.ai.generate_image(
            prompt=prompt,
            save_path=save_path,
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            provider=provider,
            progress_callback=self._on_progress,
            finished_callback=self._on_finished,
            error_callback=self._on_error
        )

    def _on_progress(self, msg: str):
        self.status_label.setText(msg)

    def _on_finished(self, save_path: str):
        self.generated_path = save_path
        self.progress.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.import_btn.setEnabled(True)
        self.status_label.setText(f"✅ 已保存: {save_path}")

        # 显示预览
        pixmap = QPixmap(save_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.preview_label.width() - 20,
                self.preview_label.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
            self.preview_label.setStyleSheet("QLabel { border: none; }")

        QMessageBox.information(self, "完成", "图片生成成功！")

    def _on_error(self, error_msg: str):
        self.progress.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.status_label.setText(f"❌ {error_msg}")
        self.preview_label.setText(f"生成失败\n{error_msg}")
        QMessageBox.critical(self, "生成失败", error_msg)

    def _import_generated(self):
        """导入生成的图片到图片库"""
        if not self.generated_path or not Path(self.generated_path).exists():
            QMessageBox.warning(self, "错误", "没有可导入的图片")
            return

        info = FileScanner.get_image_info(self.generated_path)
        if info:
            # 修改名称为 AI 生成标记
            info["name"] = f"AI_{info['name'][:20]}"

            image_id = self.db.add_image(**info)
            if image_id:
                self.config.increment_stat("total_imported")
                QMessageBox.information(
                    self, "成功", 
                    f"已导入到图片库 (ID: {image_id})\n"
                    f"关闭对话框后可在画廊中查看"
                )
            else:
                QMessageBox.warning(self, "提示", "导入失败，可能已存在")
        else:
            QMessageBox.warning(self, "错误", "无法读取图片信息")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认", "生成正在进行中，确定要取消吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.cancel()
                self.worker.wait(2000)
            else:
                event.ignore()
                return
        event.accept()
