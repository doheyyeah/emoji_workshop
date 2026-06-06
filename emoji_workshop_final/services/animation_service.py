import mimetypes
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:  # pragma: no cover - 测试环境无 PyQt6 时的回退
    class _FallbackSignal:
        def emit(self, *_args, **_kwargs):
            return None

    def pyqtSignal(*_args, **_kwargs):
        return _FallbackSignal()

    class QThread:
        def __init__(self, *_args, **_kwargs):
            pass


class AIAnimationService:
    """通用 AI 动图/短视频生成服务。"""

    DEFAULT_MODEL = "bytedance/seedance-2.0-fast"

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = (model or "").strip() or self.DEFAULT_MODEL

    def test_connection(self) -> tuple[bool, str]:
        """测试 API Key 和 Base URL 是否可用。"""
        if not self.base_url:
            return False, "未配置 Base URL"
        if not self.api_key:
            return False, "未配置 API Key"

        try:
            resp = requests.get(
                f"{self.base_url}/account",
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def generate_animation(self, prompt: str, output_path: str, timeout: int = 300, progress_callback=None) -> str:
        """创建生成任务并轮询完成后下载结果。"""
        if not prompt.strip():
            raise RuntimeError("请输入动图描述")
        if not self.base_url:
            raise RuntimeError("未配置 Base URL")
        if not self.api_key:
            raise RuntimeError("未配置 API Key")

        predictions_url = f"{self.base_url}/models/{self.model}/predictions"
        if progress_callback:
            progress_callback("正在提交任务…")

        try:
            create_resp = requests.post(
                predictions_url,
                headers=self._headers(),
                json={"input": self._build_input(prompt)},
                timeout=30,
            )
            create_resp.raise_for_status()
            prediction = create_resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"提交任务失败: {exc}") from exc

        prediction_id = prediction.get("id")
        if not prediction_id:
            raise RuntimeError("提交任务失败：未返回任务 ID")

        poll_url = f"{self.base_url}/predictions/{prediction_id}"
        deadline = time.time() + timeout
        latest = prediction

        while time.time() < deadline:
            if progress_callback:
                progress_callback("正在生成中…")
            try:
                poll_resp = requests.get(poll_url, headers=self._headers(), timeout=30)
                poll_resp.raise_for_status()
                latest = poll_resp.json()
            except requests.RequestException as exc:
                raise RuntimeError(f"轮询任务状态失败: {exc}") from exc

            status = latest.get("status")
            if status in {"succeeded", "successful"}:
                output_url = self._pick_output_url(latest.get("output"))
                if not output_url:
                    raise RuntimeError("任务成功但未返回可下载结果")
                if progress_callback:
                    progress_callback("正在下载…")
                return self._download_file(output_url, output_path)
            if status in {"failed", "canceled", "cancelled"}:
                error_msg = latest.get("error") or f"任务状态: {status}"
                raise RuntimeError(f"生成失败: {error_msg}")

            time.sleep(2)

        raise RuntimeError("生成超时，请稍后重试")

    def _build_input(self, prompt: str) -> dict:
        """构造通用文生动图输入，尽量兼容常见文生视频模型。"""
        return {
            "prompt": self._enhance_prompt(prompt),
            "duration": 5,
            "aspect_ratio": "1:1",
            "resolution": "720p",
            "generate_audio": False,
        }

    @staticmethod
    def _enhance_prompt(prompt: str) -> str:
        base_prompt = prompt.strip()
        hints = (
            "Create a short looping animated emoji sticker, centered composition, "
            "cute expressive style, smooth motion, simple clean background, "
            "high quality, no text, no watermark."
        )
        return f"{base_prompt}. {hints}"

    def _download_file(self, url: str, output_path: str) -> str:
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"下载动图失败: {exc}") from exc

        target = self._resolve_output_path(output_path, url, resp.headers.get("Content-Type", ""))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(resp.content)
        return str(target)

    @staticmethod
    def _resolve_output_path(output_path: str, url: str, content_type: str) -> Path:
        target = Path(output_path)
        suffix = AIAnimationService._guess_suffix(url, content_type)
        if suffix and target.suffix.lower() != suffix:
            target = target.with_suffix(suffix)
        return target

    @staticmethod
    def _guess_suffix(url: str, content_type: str) -> str:
        path_suffix = Path(urlparse(url).path).suffix.lower()
        if path_suffix in {".gif", ".webp", ".mp4", ".mov", ".png", ".jpg", ".jpeg"}:
            return path_suffix

        guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
        if guessed == ".jpe":
            return ".jpg"
        if guessed in {".gif", ".webp", ".mp4", ".mov", ".png", ".jpg", ".jpeg"}:
            return guessed
        return ""

    @staticmethod
    def _pick_output_url(output) -> str:
        if isinstance(output, str):
            return output
        if isinstance(output, dict):
            for key in ("url", "video", "gif", "output", "file"):
                value = output.get(key)
                if isinstance(value, str):
                    return value
            for value in output.values():
                picked = AIAnimationService._pick_output_url(value)
                if picked:
                    return picked
            return ""
        if not isinstance(output, list) or not output:
            return ""

        preferred_exts = (".gif", ".webp", ".mp4", ".mov")
        for ext in preferred_exts:
            for item in output:
                if isinstance(item, str) and ext in item.lower():
                    return item
        for item in output:
            picked = AIAnimationService._pick_output_url(item)
            if picked:
                return picked
        return ""

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


class AnimationGenerateWorker(QThread):
    """后台执行 AI 动图生成，避免阻塞 UI。"""

    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, service: AIAnimationService, prompt: str, output_path: str, timeout: int = 300, parent=None):
        super().__init__(parent)
        self.service = service
        self.prompt = prompt
        self.output_path = output_path
        self.timeout = timeout

    def run(self):
        try:
            saved_path = self.service.generate_animation(
                prompt=self.prompt,
                output_path=self.output_path,
                timeout=self.timeout,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(saved_path)
        except Exception as exc:
            self.error.emit(str(exc))
