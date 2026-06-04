"""智能推荐控制器（LLM + 视觉精排版）"""

from __future__ import annotations

import logging

from models.image_model import ImageModel
from services.database_service import DatabaseService
from services.llm_service import LLMService
from services.vision_service import VisionService
from utils.config_manager import ConfigManager


class RecommendController:
    """根据聊天上下文调用 LLM 推荐标签，可选视觉精排后返回图片"""

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
        """两阶段智能推荐

        阶段 1: 文本 LLM 选标签 → 候选集（top_k * 3）
        阶段 2（可选）: 视觉精排 → top_k

        视觉未启用：只走文本 LLM
        视觉调用失败：降级到文本 LLM 结果，并记录日志
        LLM 未启用或无 Key：直接抛出异常，不做本地降级
        """
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
            raise RuntimeError("AI 连接失败：网络不佳或 API Key 无效，请检查设置") from exc
        self.last_recommended_tags = recommended_tags

        if not recommended_tags:
            raise RuntimeError("LLM 未返回任何推荐标签")

        # 阶段 1：文本 LLM 召回候选集（top_k * 3，最多 9 张）
        candidate_count = min(top_k * 3, 9)
        rows = self.db_service.get_images_by_tags_union(recommended_tags)[:candidate_count]
        candidates = [self._row_to_dict(row) for row in rows]

        if not candidates:
            return []

        # 阶段 2（可选）：视觉精排
        get_vision = getattr(self.config_manager, "get_vision_config", None)
        vision_cfg = get_vision() if get_vision else {}
        if vision_cfg.get("enabled") and vision_cfg.get("api_key"):
            try:
                vision = VisionService(
                    base_url=vision_cfg["base_url"],
                    api_key=vision_cfg["api_key"],
                    model=vision_cfg["model"],
                )
                reranked = vision.rerank(context, candidates, top_k=top_k)
                if reranked:
                    return [ImageModel.from_db_row(self._dict_to_row(r)) for r in reranked]
            except Exception as exc:
                logging.debug("[RecommendController] 视觉精排失败，降级到文本 LLM 结果: %s", exc)

        # 降级：直接用文本 LLM 候选的前 top_k 个
        return [ImageModel.from_db_row(self._dict_to_row(r)) for r in candidates[:top_k]]

    @staticmethod
    def _row_to_dict(row) -> dict:
        """将 db 行（dict 或 tuple）统一转为 dict"""
        if isinstance(row, dict):
            return row
        return {
            "id": row[0],
            "name": row[1],
            "file_path": row[2],
            "file_type": row[3],
            "file_size": row[4] if len(row) > 4 else 0,
            "width": row[5] if len(row) > 5 else 0,
            "height": row[6] if len(row) > 6 else 0,
            "thumbnail_path": row[7] if len(row) > 7 else None,
        }

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
