import logging
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from services.providers.custom_provider import CustomProvider
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
            logging.debug("[AIService] 生成失败: %s", exc)
            self.error.emit("⚠️ AI 连接失败：网络不佳或 API Key 无效，请检查设置")


class AIService:
    """AI 生成服务外观类"""

    # 已注册的提供商
    PROVIDERS = {
        "pollinations": PollinationsProvider,
        "doubao": DoubaoProvider,
        "custom": CustomProvider,
    }

    def __init__(self):
        self.config = ConfigManager()
        self._active_workers: list[AIGenerateWorker] = []
        self.providers = {name: provider_cls() for name, provider_cls in self.PROVIDERS.items()}

    def get_enabled_providers(self) -> list[str]:
        """返回所有可选提供商 key 列表"""
        return list(self.PROVIDERS.keys())

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
        cfg = self.config.get_ai_provider_config(provider_key)
        if provider_key in ("doubao", "custom"):
            worker_kwargs["api_key"] = worker_kwargs.get("api_key") or cfg.get("api_key", "")
            worker_kwargs["model"] = worker_kwargs.get("model") or cfg.get("model", "")
        if provider_key == "custom":
            worker_kwargs["base_url"] = worker_kwargs.get("base_url") or cfg.get("base_url", "")

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
