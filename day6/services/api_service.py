import os
import requests
from pathlib import Path
from typing import Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal
from utils.config_manager import ConfigManager


class DownloadWorker(QThread):
    """异步下载工作线程

    信号：
    - progress(int, int): 当前进度，总大小
    - finished(str): 下载完成，返回保存路径
    - error(str): 下载失败，返回错误信息
    """
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, save_path: str, timeout: int = 30):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.timeout = timeout
        self._is_cancelled = False

    def run(self):
        try:
            config = ConfigManager()
            proxy = config.get("network.proxy")
            proxies = {"http": proxy, "https": proxy} if proxy else None

            response = requests.get(
                self.url, 
                stream=True, 
                timeout=self.timeout,
                proxies=proxies
            )
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            # 确保目录存在
            Path(self.save_path).parent.mkdir(parents=True, exist_ok=True)

            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._is_cancelled:
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            self.progress.emit(downloaded, total_size)

            self.finished.emit(self.save_path)

        except requests.exceptions.Timeout:
            self.error.emit("下载超时，请检查网络或增加超时时间")
        except requests.exceptions.ConnectionError:
            self.error.emit("网络连接失败，请检查网络或代理设置")
        except Exception as e:
            self.error.emit(f"下载失败: {str(e)}")

    def cancel(self):
        """取消下载"""
        self._is_cancelled = True


class APIService:
    """网络请求服务：封装 HTTP 请求和下载功能

    设计模式：外观模式（Facade），对外隐藏 requests 细节
    """

    def __init__(self):
        self.config = ConfigManager()
        self._active_workers: list[DownloadWorker] = []

    def download_image(self, url: str, filename: str = None, 
                       progress_callback: Callable = None,
                       finished_callback: Callable = None,
                       error_callback: Callable = None) -> DownloadWorker:
        """
        异步下载图片

        Args:
            url: 图片 URL
            filename: 保存文件名（不含路径），None 时从 URL 提取
            progress_callback: 进度回调 (downloaded, total)
            finished_callback: 完成回调 (save_path)
            error_callback: 错误回调 (error_msg)

        Returns:
            DownloadWorker 实例，可用于取消下载
        """
        if filename is None:
            filename = Path(url).name or "downloaded_image.jpg"

        # 保存到默认导出文件夹
        export_dir = Path(self.config.get("paths.last_export_folder", "."))
        save_path = str(export_dir / filename)

        worker = DownloadWorker(
            url, save_path, 
            timeout=self.config.get("network.api_timeout", 30)
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

    def fetch_text(self, url: str, params: dict = None) -> str:
        """同步 GET 请求，返回文本内容"""
        proxy = self.config.get("network.proxy")
        proxies = {"http": proxy, "https": proxy} if proxy else None

        response = requests.get(
            url, 
            params=params, 
            timeout=self.config.get("network.api_timeout", 30),
            proxies=proxies
        )
        response.raise_for_status()
        return response.text

    def post_json(self, url: str, data: dict = None, json_data: dict = None) -> dict:
        """同步 POST 请求，返回 JSON"""
        proxy = self.config.get("network.proxy")
        proxies = {"http": proxy, "https": proxy} if proxy else None

        response = requests.post(
            url,
            data=data,
            json=json_data,
            timeout=self.config.get("network.api_timeout", 30),
            proxies=proxies
        )
        response.raise_for_status()
        return response.json()

    def cancel_all_downloads(self):
        """取消所有进行中的下载"""
        for worker in self._active_workers:
            worker.cancel()
        self._active_workers.clear()

    def _remove_worker(self, worker: DownloadWorker):
        """移除已完成的工作线程"""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
