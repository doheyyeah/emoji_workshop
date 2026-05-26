import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple


class DatabaseService:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 数据库放在项目根目录（emoji_workshop/），而不是day3/
            project_root = Path(__file__).parent.parent.parent
            db_path = str(project_root / "emoji_workshop.db")
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # images表：存储表情包基本信息
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    file_type TEXT NOT NULL,
                    file_size INTEGER,
                    width INTEGER,
                    height INTEGER,
                    thumbnail_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def add_image(self, file_path: str, name: str, file_type: str, 
                  file_size: int = 0, width: int = 0, height: int = 0,
                  thumbnail_path: str = "") -> int:
        """添加单张图片记录，返回图片ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO images (name, file_path, file_type, file_size, 
                                       width, height, thumbnail_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, file_path, file_type, file_size, width, height, thumbnail_path))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # 路径已存在，返回已有记录的ID
                cursor.execute('SELECT id FROM images WHERE file_path = ?', (file_path,))
                return cursor.fetchone()[0]
    
    def get_all_images(self) -> List[Tuple]:
        """获取所有图片记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, file_path, file_type, file_size, width, height, thumbnail_path
                FROM images ORDER BY created_at DESC
            ''')
            return cursor.fetchall()
    
    def get_image_by_id(self, image_id: int) -> Optional[Tuple]:
        """根据ID获取单张图片"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM images WHERE id = ?', (image_id,))
            return cursor.fetchone()
    
    def delete_image(self, image_id: int) -> bool:
        """删除图片记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def clear_all(self):
        """清空所有数据（调试用）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images')
            conn.commit()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM images')
            count, total_size = cursor.fetchone()
            return {"count": count, "total_size": total_size}
