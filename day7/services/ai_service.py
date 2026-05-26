import requests
import os
from pathlib import Path
from typing import Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal
from utils.config_manager import ConfigManager


class AIGenerateWorker(QThread):
    """AI 生成工作线程（异步）

    信号：
    - progress(str): 进度状态文字
    - finished(str): 生成完成，返回保存路径
    - error(str): 生成失败，返回错误信息
    """
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt: str, save_path: str, width: int = 512, height: int = 512,
                 provider: str = "pollinations", api_key: str = None, model: str = None):
        super().__init__()
        self.prompt = prompt
        self.save_path = save_path
        self.width = width
        self.height = height
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self._is_cancelled = False

    def run(self):
        try:
            if self.provider == "pollinations":
                self._generate_pollinations()
            elif self.provider == "siliconflow":
                self._generate_siliconflow()
            else:
                self.error.emit(f"不支持的提供商: {self.provider}")
        except Exception as e:
            self.error.emit(f"生成失败: {str(e)}")

    def _generate_pollinations(self):
        """Pollinations.ai - 免费，无需注册"""
        # URL encode prompt
        import urllib.parse
        encoded_prompt = urllib.parse.quote(self.prompt)

        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={self.width}&height={self.height}"
            f"&seed=42&nologo=true&nofeed=true"
        )

        self.progress.emit("正在连接 Pollinations.ai...")

        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        # 保存图片
        Path(self.save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if self._is_cancelled:
                    return
                if chunk:
                    f.write(chunk)

        self.progress.emit("生成完成！")
        self.finished.emit(self.save_path)

    def _generate_siliconflow(self):
        """硅基流动 - 需要 API Key，支持 FLUX 等模型"""
        if not self.api_key:
            self.error.emit("硅基流动需要提供 API Key")
            return

        model = self.model or "black-forest-labs/FLUX.1-schnell"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": model,
            "prompt": self.prompt,
            "width": self.width,
            "height": self.height,
            "seed": 42
        }

        self.progress.emit("正在调用硅基流动 API...")

        response = requests.post(
            "https://api.siliconflow.cn/v1/images/generations",
            headers=headers,
            json=data,
            timeout=120
        )
        response.raise_for_status()

        result = response.json()

        # 硅基流动返回的是图片 URL
        image_url = result.get("images", [{}])[0].get("url")
        if not image_url:
            self.error.emit("API 返回格式异常")
            return

        # 下载图片
        self.progress.emit("正在下载生成的图片...")
        img_response = requests.get(image_url, timeout=60)
        img_response.raise_for_status()

        Path(self.save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.save_path, 'wb') as f:
            f.write(img_response.content)

        self.progress.emit("生成完成！")
        self.finished.emit(self.save_path)

    def cancel(self):
        self._is_cancelled = True


class AIService:
    """AI 生成服务外观类"""

    def __init__(self):
        self.config = ConfigManager()
        self._active_workers: list[AIGenerateWorker] = []

    def generate_image(self, prompt: str, save_path: str,
                       width: int = 512, height: int = 512,
                       provider: str = None,
                       progress_callback: Callable = None,
                       finished_callback: Callable = None,
                       error_callback: Callable = None) -> AIGenerateWorker:
        """
        异步生成图片

        Args:
            prompt: 图片描述文字
            save_path: 保存路径
            width/height: 图片尺寸
            provider: 提供商（pollinations/siliconflow），None 时从配置读取
        """
        if provider is None:
            provider = self.config.get("ai.provider", "pollinations")

        api_key = None
        if provider == "siliconflow":
            api_key = self.config.get("ai.siliconflow_api_key", "")

        model = self.config.get("ai.model", None)

        worker = AIGenerateWorker(
            prompt, save_path, width, height,
            provider, api_key, model
        )

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
        for worker in self._active_workers:
            worker.cancel()
        self._active_workers.clear()

    def _remove_worker(self, worker: AIGenerateWorker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
