from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

from services.api_service import APIService
from utils.config_manager import ConfigManager


class DownloadDialog(QDialog):
    """网络图片下载对话框

    功能：
    - 输入 URL 下载图片
    - 显示下载进度
    - 保存到指定文件夹
    - 下载完成后自动导入到数据库
    """

    def __init__(self, db_service, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.api = APIService()
        self.config = ConfigManager()
        self.worker = None

        self.setWindowTitle("🌐 网络图片下载")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # URL 输入
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("图片 URL:"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/image.jpg")
        url_layout.addWidget(self.url_edit)
        layout.addLayout(url_layout)

        # 保存路径
        save_layout = QHBoxLayout()
        save_layout.addWidget(QLabel("保存到:"))
        self.save_edit = QLineEdit()
        self.save_edit.setText(self.config.get("paths.last_export_folder", ""))
        self.save_edit.setReadOnly(True)
        save_layout.addWidget(self.save_edit)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._browse_folder)
        save_layout.addWidget(self.browse_btn)
        layout.addLayout(save_layout)

        # 文件名
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("文件名:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("自动从 URL 提取")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # 状态标签
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        # 按钮
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("⬇️ 开始下载")
        self.download_btn.clicked.connect(self._start_download)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_download)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹")
        if folder:
            self.save_edit.setText(folder)
            self.config.set("paths.last_export_folder", folder)

    def _start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入图片 URL")
            return

        save_dir = self.save_edit.text()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请选择保存文件夹")
            return

        filename = self.name_edit.text().strip()
        if not filename:
            # 从 URL 提取文件名
            from pathlib import Path
            filename = Path(url).name or "downloaded.jpg"

        save_path = f"{save_dir}/{filename}"

        # 更新 UI
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("正在下载...")

        # 开始下载
        self.worker = self.api.download_image(
            url=url,
            filename=filename,
            progress_callback=self._on_progress,
            finished_callback=self._on_finished,
            error_callback=self._on_error
        )

    def _on_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int(downloaded / total * 100)
            self.progress.setValue(pct)
            self.status_label.setText(f"下载中... {pct}% ({downloaded//1024}KB / {total//1024}KB)")

    def _on_finished(self, save_path: str):
        self.progress.setValue(100)
        self.status_label.setText(f"✅ 下载完成: {save_path}")
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # 询问是否导入到数据库
        reply = QMessageBox.question(
            self, "导入", "下载完成，是否导入到图片库？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._import_to_database(save_path)

    def _on_error(self, error_msg: str):
        self.progress.setVisible(False)
        self.status_label.setText(f"❌ {error_msg}")
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.critical(self, "下载失败", error_msg)

    def _cancel_download(self):
        if self.worker:
            self.worker.cancel()
            self.status_label.setText("已取消")
            self.progress.setVisible(False)
            self.download_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def _import_to_database(self, file_path: str):
        """将下载的图片导入数据库"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.file_scanner import FileScanner
        from utils.config_manager import ConfigManager

        config = ConfigManager()

        print(f"[DownloadDialog] 尝试导入: {file_path}")

        if not Path(file_path).exists():
            QMessageBox.critical(self, "错误", f"文件不存在: {file_path}")
            return

        info = FileScanner.get_image_info(file_path)
        print(f"[DownloadDialog] 解析结果: {info}")

        if info:
            image_id = self.db.add_image(**info)
            if image_id:
                QMessageBox.information(self, "成功", f"已导入到图片库 (ID: {image_id})")
                config.increment_stat("total_imported")
                print(f"[DownloadDialog] 导入成功, ID={image_id}")
            else:
                QMessageBox.warning(self, "提示", "导入失败，可能已存在")
                print(f"[DownloadDialog] 导入失败: add_image 返回 None")
        else:
            QMessageBox.warning(self, "错误", "无法读取图片信息，请检查文件格式")
            print(f"[DownloadDialog] 无法解析图片信息")
