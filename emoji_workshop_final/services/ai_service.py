import base64
from pathlib import Path
from typing import Callable
from urllib.parse import quote

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from utils.config_manager import ConfigManager


class AIProvider:
    """文生图提供商基类"""

    name = ""

    def generate(self, prompt: str, width: int = 512, height: int = 512, **kwargs) -> bytes:
        raise NotImplementedError


class PollinationsProvider(AIProvider):
    """免费兜底"""

    name = "Pollinations (免费)"

    def generate(self, prompt: str, width: int = 512, height: int = 512, **kwargs) -> bytes:
        url = (
            f"https://image.pollinations.ai/prompt/{quote(prompt)}"
            f"?width={width}&height={height}&seed={kwargs.get('seed', 42)}&nologo=true&nofeed=true"
        )
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        return response.content


class DoubaoProvider(AIProvider):
    """豆包（火山引擎）"""

    name = "豆包 (火山引擎)"
    endpoint = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

    def generate(self, prompt: str, width: int = 1024, height: int = 1024, **kwargs) -> bytes:
        api_key = kwargs.get("api_key", "")
        if not api_key:
            raise RuntimeError("缺少 API Key")

        model = kwargs.get("model", "doubao-seedream-3-0-t2i-250415")
        response = requests.post(
            self.endpoint,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={
                "model": model,
                "prompt": prompt,
                "size": f"{width}x{height}",
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or []
        if not data:
            raise RuntimeError("返回内容为空")
        first = data[0]
        b64_data = first.get("b64_json")
        image_url = first.get("url")
        if b64_data:
            return base64.b64decode(b64_data)
        if image_url:
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            return img_resp.content
        raise RuntimeError("返回格式不支持")


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

    def __init__(self):
        self.config = ConfigManager()
        self._active_workers: list[AIGenerateWorker] = []
        self.providers = {
            "pollinations": PollinationsProvider(),
            "doubao": DoubaoProvider(),
        }

    def get_enabled_providers(self) -> list[str]:
        enabled = self.config.get("ai.enabled_providers", ["pollinations"])
        if "pollinations" not in enabled:
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
            worker_kwargs["api_key"] = self.config.get("ai.doubao_api_key", "")
            worker_kwargs["model"] = self.config.get("ai.model", "doubao-seedream-3-0-t2i-250415")

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
