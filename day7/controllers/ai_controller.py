"""AI 生成控制器

职责：
- 协调 AI 生成对话框与主窗口的交互
- 管理生成状态
- 处理生成完成后的回调（刷新画廊等）

设计模式：中介者模式（Mediator）
"""

from PyQt6.QtCore import QObject, pyqtSignal
from services.ai_service import AIService
from services.database_service import DatabaseService
from utils.config_manager import ConfigManager


class AIController(QObject):
    """AI 生成业务控制器"""

    # 信号：通知主窗口刷新
    image_imported = pyqtSignal(int)  # 返回导入的图片 ID
    generation_started = pyqtSignal()
    generation_finished = pyqtSignal(bool, str)  # 成功/失败, 消息

    def __init__(self, db_service: DatabaseService, parent=None):
        super().__init__(parent)
        self.db = db_service
        self.ai = AIService()
        self.config = ConfigManager()

    def open_generate_dialog(self, parent_widget=None):
        """打开 AI 生成对话框"""
        from views.ai_generate_dialog import AIGenerateDialog
        dialog = AIGenerateDialog(self.db, parent_widget)

        # 连接信号
        dialog.finished.connect(lambda: self._on_dialog_closed(dialog))

        dialog.exec()

    def _on_dialog_closed(self, dialog):
        """对话框关闭后的处理"""
        # 如果有新图片生成，通知主窗口刷新
        pass

    def get_available_providers(self) -> list:
        """获取可用的 AI 提供商列表"""
        providers = [
            {"id": "pollinations", "name": "Pollinations.ai", "free": True, "needs_key": False},
            {"id": "siliconflow", "name": "硅基流动", "free": False, "needs_key": True},
        ]
        return providers

    def validate_api_key(self, provider: str, api_key: str) -> bool:
        """验证 API Key 是否有效（简单检查格式）"""
        if provider == "siliconflow":
            return api_key.startswith("sk-") and len(api_key) > 20
        return True
