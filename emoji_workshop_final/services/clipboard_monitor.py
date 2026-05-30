"""剪贴板监听服务"""

from hashlib import md5

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication


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
        if mime and mime.hasImage():
            image = self.clipboard.image()
            if not image.isNull():
                ba = image.bits().asstring(image.sizeInBytes())
                h = md5(ba).hexdigest()
                if h != self._last_image_hash:
                    self._last_image_hash = h
                    self.new_image_detected.emit(image)
