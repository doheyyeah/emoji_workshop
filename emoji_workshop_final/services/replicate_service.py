import time
from pathlib import Path

import requests

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except Exception:  # pragma: no cover - 测试环境无 PyQt6 时回退
    class _FallbackSignal:
        def emit(self, *_args, **_kwargs):
            return None

    def pyqtSignal(*_args, **_kwargs):
        return _FallbackSignal()

    class QThread:
        def __init__(self, *_args, **_kwargs):
            pass


class ReplicateService:
    """Replicate 动图生成服务（fofr/sticker-maker）"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model.strip() or "fofr/sticker-maker"

    def test_connection(self) -> tuple[bool, str]:
        """测试 Replicate token 可用性"""
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

    def generate_sticker(self, prompt: str, output_path: str, timeout: int = 300, progress_callback=None) -> str:
        """创建预测任务并轮询，下载 GIF 到 output_path"""
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
                json={"input": {"prompt": prompt}},
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
            if status == "succeeded":
                output_url = self._pick_output_url(latest.get("output"))
                if not output_url:
                    raise RuntimeError("任务成功但未返回可下载结果")
                if progress_callback:
                    progress_callback("正在下载…")
                return self._download_file(output_url, output_path)
            if status in {"failed", "canceled"}:
                error_msg = latest.get("error") or f"任务状态: {status}"
                raise RuntimeError(f"生成失败: {error_msg}")

            time.sleep(2)

        raise RuntimeError("生成超时，请稍后重试")

    def _download_file(self, url: str, output_path: str) -> str:
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"下载 GIF 失败: {exc}") from exc

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(resp.content)
        return str(target)

    @staticmethod
    def _pick_output_url(output) -> str:
        if isinstance(output, str):
            return output
        if not isinstance(output, list) or not output:
            return ""
        for item in output:
            if isinstance(item, str) and ".gif" in item.lower():
                return item
        for item in output:
            if isinstance(item, str):
                return item
        return ""

    def _headers(self) -> dict:
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }


class StickerGenerateWorker(QThread):
    """后台执行 Replicate 动图生成，避免阻塞 UI"""

    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, service: ReplicateService, prompt: str, output_path: str, timeout: int = 300, parent=None):
        super().__init__(parent)
        self.service = service
        self.prompt = prompt
        self.output_path = output_path
        self.timeout = timeout

    def run(self):
        try:
            saved_path = self.service.generate_sticker(
                prompt=self.prompt,
                output_path=self.output_path,
                timeout=self.timeout,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(saved_path)
        except Exception as exc:
            self.error.emit(str(exc))
