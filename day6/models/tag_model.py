from dataclasses import dataclass
from typing import Optional


@dataclass
class TagModel:
    """标签数据实体"""
    id: int = 0
    name: str = ""
    color: str = "#FF6B6B"  # 默认红色
    
    @classmethod
    def from_db_row(cls, row: tuple) -> 'TagModel':
        """从数据库行创建对象"""
        return cls(
            id=row[0],
            name=row[1],
            color=row[2] if len(row) > 2 else "#FF6B6B"
        )