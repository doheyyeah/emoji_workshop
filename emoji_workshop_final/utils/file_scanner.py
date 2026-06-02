import os
import logging
from pathlib import Path
from typing import List, Tuple
from PIL import Image


class FileScanner:
    """文件夹扫描器，提取图片信息"""

    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    EXCLUDE_DIRS = {
        "venv", ".venv", "env", "__pycache__", ".git",
        "site-packages", "node_modules", ".idea", ".vscode",
        "dist", "build", ".pytest_cache",
    }

    @classmethod
    def scan_directory(cls, root_path: str) -> list[str]:
        """扫描目录并返回图片文件路径列表（跳过无关目录）"""
        results: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in cls.EXCLUDE_DIRS]
            for filename in filenames:
                if Path(filename).suffix.lower() in cls.SUPPORTED_FORMATS:
                    results.append(str(Path(dirpath) / filename))
        return results
    
    @classmethod
    def scan_folder(cls, folder_path: str) -> List[dict]:
        """
        扫描文件夹中的所有图片
        返回: [{file_path, name, file_type, file_size, width, height}, ...]
        """
        results = []
        folder = Path(folder_path)
        
        if not folder.exists():
            return results
        
        for file_path_str in cls.scan_directory(str(folder)):
            file_path = Path(file_path_str)
            try:
                # 获取图片尺寸
                with Image.open(file_path) as img:
                    width, height = img.size

                info = {
                    'file_path': str(file_path.absolute()),
                    'name': file_path.stem,
                    'file_type': file_path.suffix.lower().replace('.', ''),
                    'file_size': file_path.stat().st_size,
                    'width': width,
                    'height': height
                }
                results.append(info)
            except Exception as e:
                logging.debug("无法读取图片 %s: %s", file_path, e)
        
        return results
    
    @classmethod
    def get_image_info(cls, file_path: str) -> dict:
        """获取单张图片的详细信息"""
        path = Path(file_path)
        if not path.exists() or path.suffix.lower() not in cls.SUPPORTED_FORMATS:
            return {}
        
        with Image.open(path) as img:
            width, height = img.size
        
        return {
            'file_path': str(path.absolute()),
            'name': path.stem,
            'file_type': path.suffix.lower().replace('.', ''),
            'file_size': path.stat().st_size,
            'width': width,
            'height': height
        }