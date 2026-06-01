import base64
from pathlib import Path
from typing import Callable
from urllib.parse import quote

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from services.providers.doubao_provider import DoubaoProvider
from services.providers.pollinations_provider import PollinationsProvider
from utils.config_manager import ConfigManager


class AIProvider:
    """文生图提供商基类"""

    name = ""

    def generate(self, prompt: str, width: int = 512, height: int = 512, **kwargs) -> bytes:
        raise NotImplementedError


class AIGenerateWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, provider: AIProvider, prompt: str, save_path: str, width: int, height: int, **kwargs):
        super().__init__()
        self.provider = provider
        self.prompt = prompt
        self.save_path = save_path
        self.width = width
        self.height = height
        self.kwargs = kwargs

    def run(self):
        try:
            self.progress.emit("正在生成图片...")
            content = self.provider.generate(self.prompt, self.width, self.height, **self.kwargs)
            if self.isInterruptionRequested():
                return
            Path(self.save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.save_path, "wb") as f:
                f.write(content)
            self.finished.emit(self.save_path)
        except Exception as exc:
            print(f"[AIService] 生成失败: {exc}")
            self.error.emit("生成失败,请检查 API Key 或更换提供商")


class AIService:
    """AI 生成服务外观类"""

    # 已注册的提供商
    PROVIDERS = {
        "pollinations": PollinationsProvider(),
        "doubao": DoubaoProvider(),
    }

    def __init__(self):
        self.config = ConfigManager()
        self._active_workers: list[AIGenerateWorker] = []
        self.providers = self.PROVIDERS

    def get_enabled_providers(self) -> list[str]:
        """返回当前已启用的提供商 key 列表（pollinations 始终保留）"""
        ai_cfg = self.config.get_ai_provider_config()
        enabled = []
        # 豆包（需要 api_key）
        doubao_cfg = ai_cfg.get("doubao", {})
        if doubao_cfg.get("enabled") or doubao_cfg.get("api_key"):
            enabled.append("doubao")
        # Pollinations 始终可用
        enabled.append("pollinations")
        return enabled

    def generate_image(
        self,
        prompt: str,
        save_path: str,
        width: int = 512,
        height: int = 512,
        provider: str = None,
        progress_callback: Callable = None,
        finished_callback: Callable = None,
        error_callback: Callable = None,
        **kwargs
    ) -> AIGenerateWorker:
        provider_key = provider or self.config.get("ai.provider", "pollinations")
        provider_obj = self.providers.get(provider_key, self.providers["pollinations"])

        worker_kwargs = dict(kwargs)
        if provider_key == "doubao":
            ai_cfg = self.config.get_ai_provider_config()
            worker_kwargs["api_key"] = ai_cfg["doubao"].get("api_key") or self.config.get("ai.doubao_api_key", "")
            worker_kwargs["model"] = ai_cfg["doubao"].get("model", "doubao-seedream-5-0-260128")

        worker = AIGenerateWorker(provider_obj, prompt, save_path, width, height, **worker_kwargs)

        if progress_callback:
            worker.progress.connect(progress_callback)
        if finished_callback:
            worker.finished.connect(finished_callback)
        if error_callback:
            worker.error.connect(error_callback)

        self._active_workers.append(worker)
        worker.finished.connect(lambda _: self._remove_worker(worker))
        worker.error.connect(lambda _: self._remove_worker(worker))
        worker.start()
        return worker

    def cancel_all(self):
        for worker in list(self._active_workers):
            worker.requestInterruption()
        self._active_workers.clear()

    def _remove_worker(self, worker: AIGenerateWorker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
