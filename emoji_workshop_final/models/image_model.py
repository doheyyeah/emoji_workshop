from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ImageModel:
    """表情包数据实体"""
    id: int = 0
    name: str = ""
    file_path: str = ""
    file_type: str = ""
    file_size: int = 0
    width: int = 0
    height: int = 0
    thumbnail_path: Optional[str] = None
    
    @property
    def display_name(self) -> str:
        """显示名称（去掉扩展名）"""
        return Path(self.file_path).stem
    
    @property
    def is_gif(self) -> bool:
        """是否为GIF动图"""
        return self.file_type.lower() == 'gif'
    
    @classmethod
    def from_db_row(cls, row: tuple) -> 'ImageModel':
        """从数据库行创建对象"""
        # row: (id, name, file_path, file_type, file_size, width, height, thumbnail_path, ...)
        return cls(
            id=row[0],
            name=row[1],
            file_path=row[2],
            file_type=row[3],
            file_size=row[4] if len(row) > 4 else 0,
            width=row[5] if len(row) > 5 else 0,
            height=row[6] if len(row) > 6 else 0,
            thumbnail_path=row[7] if len(row) > 7 else None
        )