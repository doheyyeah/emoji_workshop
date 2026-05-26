import json
import os
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    """应用配置管理器：JSON 持久化，支持嵌套键

    设计模式：单例（通过模块级实例共享）
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_name: str = "emoji_workshop_config.json"):
        if self._initialized:
            return
        self._initialized = True

        # 配置文件放在用户目录下的 .emoji_workshop/ 中（跨平台）
        self.config_dir = Path.home() / ".emoji_workshop"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / config_name

        # 默认配置
        self._defaults = {
            "window": {
                "width": 1200,
                "height": 700,
                "pos_x": 100,
                "pos_y": 100,
                "maximized": False
            },
            "ui": {
                "theme": "dark",           # dark / light
                "thumbnail_size": 128,      # 缩略图尺寸
                "grid_spacing": 10,         # 网格间距
                "preview_panel_width": 500  # 预览面板宽度
            },
            "paths": {
                "last_import_folder": str(Path.home() / "Pictures"),
                "last_export_folder": str(Path.home() / "Desktop"),
                "cache_dir": None           # None 表示使用默认
            },
            "network": {
                "api_timeout": 30,
                "max_concurrent_downloads": 3,
                "proxy": None               # 代理设置
            },
            "behavior": {
                "auto_save": True,          # 修改后自动保存配置
                "confirm_delete": True,     # 删除前确认
                "recent_folders": [],       # 最近导入的文件夹（最多10个）
                "recent_files": []          # 最近打开的文件（最多10个）
            },
            "stats": {
                "total_imported": 0,        # 累计导入图片数
                "total_tags_created": 0,    # 累计创建标签数
                "launch_count": 0           # 启动次数
            }
        }

        self._config = {}
        self._load()

    def _load(self) -> None:
        """从文件加载配置，合并到默认值"""
        self._config = self._deep_copy(self._defaults)

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                self._deep_merge(self._config, loaded)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[ConfigManager] 配置加载失败，使用默认配置: {e}")

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            print(f"[ConfigManager] 配置保存失败: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，支持点号分隔的嵌套键，如 'window.width'"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置项，支持点号分隔的嵌套键"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

        if self.get("behavior.auto_save", True):
            self.save()

    def reset_to_default(self, key: Optional[str] = None) -> None:
        """重置配置：key=None 重置全部，否则重置指定键"""
        if key is None:
            self._config = self._deep_copy(self._defaults)
        else:
            default_val = self._get_default_by_key(key)
            if default_val is not None:
                self.set(key, default_val)
        self.save()

    def add_recent_folder(self, folder_path: str) -> None:
        """添加最近文件夹（去重，最多保留10个）"""
        recent = self.get("behavior.recent_folders", [])
        # 去重并移到最前
        recent = [f for f in recent if f != folder_path]
        recent.insert(0, folder_path)
        recent = recent[:10]
        self.set("behavior.recent_folders", recent)

    def increment_stat(self, stat_key: str) -> None:
        """递增统计计数器"""
        current = self.get(f"stats.{stat_key}", 0)
        self.set(f"stats.{stat_key}", current + 1)

    # ===== 内部工具方法 =====

    def _deep_copy(self, obj: Any) -> Any:
        """深拷贝"""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        return obj

    def _deep_merge(self, base: dict, override: dict) -> None:
        """递归合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _get_default_by_key(self, key: str) -> Any:
        """根据键从默认值中获取"""
        keys = key.split('.')
        value = self._defaults
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value
