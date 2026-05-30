"""智能推荐控制器（LLM 版）"""

from __future__ import annotations

from models.image_model import ImageModel
from services.database_service import DatabaseService
from services.llm_service import LLMService
from utils.config_manager import ConfigManager


class RecommendController:
    """根据聊天上下文调用 LLM 推荐标签并返回图片"""

    def __init__(
        self,
        db_service: DatabaseService,
        config_manager: ConfigManager | None = None,
        llm_service_cls=LLMService,
    ) -> None:
        self.db_service = db_service
        self.config_manager = config_manager or ConfigManager()
        self.llm_service_cls = llm_service_cls
        self.last_recommended_tags: list[str] = []

    def recommend(self, context: str, top_k: int = 3) -> list[ImageModel]:
        """智能推荐"""
        config = self.config_manager.get_llm_config()
        if not config.get("enabled"):
            raise RuntimeError("未启用 LLM 智能推荐，请到 设置 → AI 推荐 中开启")
        if not config.get("api_key"):
            raise RuntimeError("未配置 API Key，请到 设置 → AI 推荐 中填写")

        all_tags = [t[1] for t in self.db_service.get_all_tags()]
        if not all_tags:
            raise RuntimeError("当前库中没有任何标签，请先给图片打标签")

        llm = self.llm_service_cls(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["model"],
        )
        try:
            recommended_tags = llm.recommend_tags(context, all_tags, top_k=top_k)
        except Exception as exc:
            raise RuntimeError("LLM 调用失败，请检查 API Key 或网络设置") from exc
        self.last_recommended_tags = recommended_tags

        if not recommended_tags:
            raise RuntimeError("LLM 未返回任何推荐标签")

        rows = self.db_service.get_images_by_tags_union(recommended_tags)[:top_k]
        return [ImageModel.from_db_row(self._dict_to_row(row)) for row in rows]

    @staticmethod
    def _dict_to_row(row: dict) -> tuple:
        return (
            row["id"],
            row["name"],
            row["file_path"],
            row["file_type"],
            row.get("file_size", 0),
            row.get("width", 0),
            row.get("height", 0),
            row.get("thumbnail_path"),
        )
