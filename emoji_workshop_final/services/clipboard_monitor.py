"""剪贴板监听服务"""

from hashlib import md5

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from services.clipboard_service import ClipboardService


class ClipboardMonitor(QObject):
    new_image_detected = pyqtSignal(QImage)

    def __init__(self):
        super().__init__()
        self.enabled = False
        self._last_image_hash = None
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self._on_clipboard_change)

    def start(self):
        self.enabled = True

    def stop(self):
        self.enabled = False

    def _on_clipboard_change(self):
        if not self.enabled:
            return
        mime = self.clipboard.mimeData()
        if not mime or not mime.hasImage():
            return
        # 跳过表情工坊内部复制的图片（如双击图片库 / 智能推荐里的图片），
        # 仅对来自应用外部（在其它程序里复制）的图片提示是否入库。
        if mime.hasFormat(ClipboardService.INTERNAL_MIME_TYPE):
            # 记录其哈希，避免后续相同图片再次触发提示
            image = self.clipboard.image()
            if not image.isNull():
                ba = image.bits().asstring(image.sizeInBytes())
                self._last_image_hash = md5(ba).hexdigest()
            return
        image = self.clipboard.image()
        if not image.isNull():
            ba = image.bits().asstring(image.sizeInBytes())
            h = md5(ba).hexdigest()
            if h != self._last_image_hash:
                self._last_image_hash = h
                self.new_image_detected.emit(image)
