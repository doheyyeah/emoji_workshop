import os
import hashlib
from pathlib import Path
from typing import Optional
from PIL import Image


class ThumbnailService:
    """缩略图生成与缓存服务"""
    
    THUMB_SIZE = 128  # 缩略图尺寸
    QUALITY = 85      # JPEG质量
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            # 默认放在 day4/resources/thumbnails/
            self.cache_dir = Path(__file__).parent.parent / "resources" / "thumbnails"
        else:
            self.cache_dir = Path(cache_dir)
        
        # 确保目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, file_path: str) -> Path:
        """根据原图路径生成缓存文件名（MD5哈希）"""
        # 用文件路径+修改时间作为唯一标识
        path_obj = Path(file_path)
        mtime = str(path_obj.stat().st_mtime) if path_obj.exists() else "0"
        unique_str = f"{file_path}:{mtime}"
        
        hash_name = hashlib.md5(unique_str.encode()).hexdigest()
        return self.cache_dir / f"{hash_name}.jpg"
    
    def get_thumbnail(self, file_path: str) -> Optional[str]:
        """
        获取缩略图路径。如果缓存不存在则生成。
        返回: 缩略图文件路径，或 None（生成失败）
        """
        if not Path(file_path).exists():
            return None
        
        cache_path = self._get_cache_path(file_path)
        
        # 缓存已存在，直接返回
        if cache_path.exists():
            return str(cache_path)
        
        # 生成缩略图
        return self._generate_thumbnail(file_path, cache_path)
    
    def _generate_thumbnail(self, src_path: str, dst_path: Path) -> Optional[str]:
        """用 Pillow 生成缩略图"""
        try:
            with Image.open(src_path) as img:
                # 转换为 RGB（处理 PNG 透明通道等）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # 等比例缩放
                img.thumbnail((self.THUMB_SIZE, self.THUMB_SIZE), Image.Resampling.LANCZOS)
                
                # 保存为 JPEG
                img.save(dst_path, 'JPEG', quality=self.QUALITY)
                
                return str(dst_path)
        except Exception as e:
            print(f"缩略图生成失败 {src_path}: {e}")
            return None
    
    def clear_cache(self):
        """清空所有缩略图缓存"""
        for f in self.cache_dir.glob("*.jpg"):
            f.unlink()
    
    def get_cache_size(self) -> int:
        """获取缓存文件数量"""
        return len(list(self.cache_dir.glob("*.jpg")))