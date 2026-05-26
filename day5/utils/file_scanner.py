import os
from pathlib import Path
from typing import List, Tuple
from PIL import Image


class FileScanner:
    """文件夹扫描器，提取图片信息"""
    
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
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
        
        # 递归遍历
        for file_path in folder.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in cls.SUPPORTED_FORMATS:
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
                    print(f"无法读取图片 {file_path}: {e}")
        
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