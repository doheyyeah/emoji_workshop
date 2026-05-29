"""剪贴板服务 - 支持 GIF 动图保留发送

核心原理:
Windows 剪贴板有两种图片格式:
1. CF_BITMAP/CF_DIB:位图数据(单帧,GIF 会丢失动画)
2. CF_HDROP:文件路径引用(微信/QQ 读取原始文件,保留动画)

本服务同时设置两种格式,让目标应用自己选最适合的:
- 微信/QQ/钉钉粘贴时:识别为文件 → 保留动图
- 网页/Word 粘贴时:识别为图片 → 静态首帧(兜底)
"""
from pathlib import Path
from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication


class ClipboardService:
    """统一的剪贴板复制服务,适配静图和动图"""

    @staticmethod
    def copy_image(file_path: str) -> bool:
        """复制图片到剪贴板,同时支持文件粘贴(保留动图)和图片粘贴(静态兜底)

        Args:
            file_path: 图片文件的绝对路径(支持 .png/.jpg/.gif/.webp 等)

        Returns:
            True 表示复制成功
        """
        path = Path(file_path)
        if not path.exists():
            return False

        mime = QMimeData()

        # 格式 1:文件 URL(微信/QQ 优先识别,保留动图)
        mime.setUrls([QUrl.fromLocalFile(str(path.absolute()))])

        # 格式 2:位图(网页/Word 等场景的兜底)
        image = QImage(str(path))
        if not image.isNull():
            mime.setImageData(image)

        QApplication.clipboard().setMimeData(mime)
        return True

    @staticmethod
    def is_animated(file_path: str) -> bool:
        """判断是否为动图(GIF / WebP 动图)"""
        suffix = Path(file_path).suffix.lower()
        return suffix in {'.gif', '.webp'}
