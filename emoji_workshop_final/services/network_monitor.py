"""AI API 网络状态监控"""

from __future__ import annotations

import time

import requests
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class NetworkMonitor(QObject):
    """后台定时检查常用 AI API 连通性"""

    # provider_name, is_online, latency_ms
    status_changed = pyqtSignal(str, bool, int)

    APIS = {
        "kimi": "https://api.moonshot.cn/v1/models",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4/models",
        "doubao": "https://ark.cn-beijing.volces.com/api/v3/models",
    }

    def __init__(self, config_manager, interval_sec: int = 60):
        super().__init__()
        self.config = config_manager
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_all)
        self.timer.setInterval(interval_sec * 1000)

    def start(self):
        self.check_all()
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def check_all(self):
        """检查所有 API 连通性（最小可行实现）"""
        for name, url in self.APIS.items():
            key = self._get_key(name)
            if not key:
                self.status_changed.emit(name, False, -1)
                continue
            try:
                t0 = time.time()
                resp = requests.get(
                    url,
                    headers={"Authorization": "Bearer " + key},
                    timeout=3,
                )
                latency = int((time.time() - t0) * 1000)
                online = resp.status_code in (200, 401, 403)
                self.status_changed.emit(name, online, latency if online else -1)
            except Exception:
                self.status_changed.emit(name, False, -1)

    def _get_key(self, name: str) -> str:
        if name == "kimi":
            return self.config.get_llm_config().get("api_key", "")
        if name == "zhipu":
            return self.config.get_vision_config().get("api_key", "")
        if name == "doubao":
            return self.config.get_ai_provider_config("doubao").get("api_key", "")
        return ""
