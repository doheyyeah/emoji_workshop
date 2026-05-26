import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple


class DatabaseService:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 数据库放在项目根目录（emoji_workshop/）
            project_root = Path(__file__).parent.parent.parent
            db_path = str(project_root / "emoji_workshop.db")
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构（IF NOT EXISTS 保证升级安全）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # images表（已存在，不报错）
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
            
            # ===== Day5 新增：标签系统 =====
            # tags表：标签
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT DEFAULT '#FF6B6B'
                )
            ''')
            
            # image_tags表：多对多关联
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS image_tags (
                    image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
                    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (image_id, tag_id)
                )
            ''')
            
            conn.commit()
    
    # ===== images 相关方法（原有，不改）=====
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
        """删除图片记录（级联删除标签关联）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def clear_all(self):
        """清空所有数据"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM image_tags')
            cursor.execute('DELETE FROM tags')
            cursor.execute('DELETE FROM images')
            conn.commit()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM images')
            count, total_size = cursor.fetchone()
            return {"count": count, "total_size": total_size}
    
    # ===== Day5 新增：标签相关方法 =====
    
    def add_tag(self, name: str, color: str = "#FF6B6B") -> int:
        """添加标签，返回标签ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO tags (name, color) VALUES (?, ?)', (name, color))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # 标签已存在，返回已有ID
                cursor.execute('SELECT id FROM tags WHERE name = ?', (name,))
                return cursor.fetchone()[0]
    
    def get_all_tags(self) -> List[Tuple]:
        """获取所有标签"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, color FROM tags ORDER BY name')
            return cursor.fetchall()
    
    def delete_tag(self, tag_id: int):
        """删除标签（级联删除关联）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM image_tags WHERE tag_id = ?', (tag_id,))
            cursor.execute('DELETE FROM tags WHERE id = ?', (tag_id,))
            conn.commit()
    
    def add_image_tag(self, image_id: int, tag_id: int):
        """给图片打标签"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?)',
                              (image_id, tag_id))
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # 已存在，忽略
    
    def remove_image_tag(self, image_id: int, tag_id: int):
        """移除图片的标签"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM image_tags WHERE image_id = ? AND tag_id = ?',
                          (image_id, tag_id))
            conn.commit()
    
    def get_image_tags(self, image_id: int) -> List[Tuple]:
        """获取图片的所有标签"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.id, t.name, t.color 
                FROM tags t
                JOIN image_tags it ON t.id = it.tag_id
                WHERE it.image_id = ?
            ''', (image_id,))
            return cursor.fetchall()
    
    def search_images_by_tags(self, tag_ids: List[int]) -> List[Tuple]:
        """按标签筛选图片（多选交集：必须同时包含所有选中标签）"""
        if not tag_ids:
            return self.get_all_images()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 使用 GROUP BY + HAVING 实现交集
            placeholders = ','.join('?' * len(tag_ids))
            query = f'''
                SELECT i.id, i.name, i.file_path, i.file_type, i.file_size, 
                       i.width, i.height, i.thumbnail_path
                FROM images i
                JOIN image_tags it ON i.id = it.image_id
                WHERE it.tag_id IN ({placeholders})
                GROUP BY i.id
                HAVING COUNT(DISTINCT it.tag_id) = ?
                ORDER BY i.created_at DESC
            '''
            cursor.execute(query, tag_ids + [len(tag_ids)])
            return cursor.fetchall()
    
    def search_images_by_name(self, keyword: str) -> List[Tuple]:
        """按名称搜索图片"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, file_path, file_type, file_size, width, height, thumbnail_path
                FROM images WHERE name LIKE ? ORDER BY created_at DESC
            ''', (f'%{keyword}%',))
            return cursor.fetchall()