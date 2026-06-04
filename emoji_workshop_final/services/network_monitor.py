"""AI API 网络状态监控"""

from __future__ import annotations

import time

import requests
from PyQt6.QtCore import QObject, QThread, pyqtSignal


class _NetworkCheckWorker(QThread):
    """后台执行一次连通性检测"""

    status_found = pyqtSignal(str, bool, int)

    def __init__(self, apis: dict[str, str], key_getter, parent=None):
        super().__init__(parent)
        self._apis = apis
        self._key_getter = key_getter

    def run(self):
        for name, url in self._apis.items():
            if self.isInterruptionRequested():
                return
            key = self._key_getter(name)
            if not key:
                self.status_found.emit(name, False, -1)
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
                self.status_found.emit(name, online, latency if online else -1)
            except Exception:
                self.status_found.emit(name, False, -1)


class NetworkMonitor(QObject):
    """按需检查常用 AI API 连通性（后台线程）"""

    # provider_name, is_online, latency_ms
    status_changed = pyqtSignal(str, bool, int)

    APIS = {
        "kimi": "https://api.moonshot.cn/v1/models",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4/models",
        "doubao": "https://ark.cn-beijing.volces.com/api/v3/models",
    }

    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self._worker = None

    def start(self):
        """兼容旧接口：触发一次按需检查"""
        self.check_all()

    def stop(self):
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(1000)
        self._worker = None

    def check_all(self):
        """后台检查所有 API 连通性"""
        if self._worker and self._worker.isRunning():
            return
        self._worker = _NetworkCheckWorker(self.APIS, self._get_key, self)
        self._worker.status_found.connect(self.status_changed)
        self._worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker.start()

    def _get_key(self, name: str) -> str:
        if name == "kimi":
            return self.config.get_llm_config().get("api_key", "")
        if name == "zhipu":
            return self.config.get_vision_config().get("api_key", "")
        if name == "doubao":
            return self.config.get_ai_provider_config("doubao").get("api_key", "")
        return ""
