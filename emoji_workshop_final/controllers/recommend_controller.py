"""智能推荐控制器（LLM + 视觉精排版）"""

from __future__ import annotations

import hashlib
import logging
import re

from models.image_model import ImageModel
from services.database_service import DatabaseService
from services.llm_service import LLMService
from services.vision_service import VisionService
from utils.config_manager import ConfigManager


class RecommendController:
    """根据聊天上下文调用 LLM 推荐标签，可选视觉精排后返回图片"""

    CANDIDATE_MULTIPLIER = 5
    MIN_CANDIDATE_COUNT = 20
    MAX_CANDIDATE_COUNT = 30

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
        self.last_debug_info: dict = {}

    def recommend(self, context: str, top_k: int = 3) -> list[ImageModel]:
        """智能推荐：LLM 粗筛候选 + 本地补齐 + 视觉精排"""
        llm_cfg = self.config_manager.get_llm_config()
        get_vision = getattr(self.config_manager, "get_vision_config", None)
        vision_cfg = get_vision() if get_vision else {}

        all_images = self.db_service.get_all_images_with_tags()
        if not all_images:
            return []

        available_tags = sorted({tag for img in all_images for tag in img.get("tags", [])})
        local_keywords = self._extract_keywords(context)
        candidate_count = self._calc_candidate_count(top_k)

        llm_tags: list[str] = []
        llm_keywords: list[str] = []
        llm_image_ids: list[int] = []
        llm_reason = ""
        llm_status = "未启用"
        fallback_notes: list[str] = []

        if llm_cfg.get("enabled"):
            if llm_cfg.get("api_key"):
                llm = self.llm_service_cls(
                    base_url=llm_cfg["base_url"],
                    api_key=llm_cfg["api_key"],
                    model=llm_cfg["model"],
                )
                summaries = [
                    {"id": img.get("id"), "name": img.get("name", ""), "tags": img.get("tags", [])}
                    for img in all_images
                ]
                try:
                    if hasattr(llm, "select_candidate_images"):
                        analysis = llm.select_candidate_images(
                            context=context,
                            image_summaries=summaries,
                            available_tags=available_tags,
                            candidate_count=candidate_count,
                        )
                    else:
                        analysis = llm.analyze_recommendation(
                            context=context,
                            image_summaries=summaries,
                            available_tags=available_tags,
                            top_k=max(top_k, 5),
                        )
                    llm_tags = analysis.get("tags", [])
                    llm_keywords = analysis.get("keywords", [])
                    llm_image_ids = analysis.get("image_ids", [])
                    llm_reason = analysis.get("reason", "")
                    llm_status = "成功"
                except Exception as exc:
                    llm_status = "失败"
                    fallback_notes.append("LLM 调用失败，已降级本地召回")
                    logging.debug("[RecommendController] LLM 分析失败，降级本地召回: %s", exc)
            else:
                llm_status = "未配置Key"
                fallback_notes.append("LLM 已启用但未配置 API Key")

        self.last_recommended_tags = list(llm_tags)

        ranked_all = self._rank_candidates(
            context=context,
            all_images=all_images,
            llm_tags=llm_tags,
            llm_keywords=llm_keywords,
            llm_image_ids=llm_image_ids,
            local_keywords=local_keywords,
        )
        candidates, llm_seed_count = self._build_candidate_scope(
            ranked_all=ranked_all,
            preferred_ids=llm_image_ids,
            candidate_count=candidate_count,
        )
        if llm_status == "成功" and llm_seed_count == 0:
            fallback_notes.append("LLM 粗筛无有效候选，已降级本地文本匹配")
        elif llm_status == "成功" and llm_seed_count < candidate_count:
            fallback_notes.append("LLM 候选不足，已使用本地文本匹配补齐")

        vision_status = "未启用"
        selected_rows = candidates[:top_k]
        if vision_cfg.get("enabled"):
            if vision_cfg.get("api_key"):
                try:
                    vision = VisionService(
                        base_url=vision_cfg["base_url"],
                        api_key=vision_cfg["api_key"],
                        model=vision_cfg["model"],
                    )
                    reranked = vision.rerank(
                        context=context,
                        candidate_images=candidates,
                        top_k=top_k,
                        max_images=len(candidates),
                    )
                    if reranked:
                        selected_rows = reranked
                    vision_status = "成功"
                except Exception as exc:
                    vision_status = "失败"
                    if llm_status == "成功":
                        fallback_notes.append("视觉精排失败，已降级为 LLM 粗筛 + 本地文本排序")
                    else:
                        fallback_notes.append("视觉精排失败，已降级本地文本排序")
                    logging.debug("[RecommendController] 视觉精排失败，降级文本排序: %s", exc)
            else:
                vision_status = "未配置Key"
                fallback_notes.append("视觉精排已启用但未配置 API Key")

        if llm_status == "未启用" and vision_status == "未启用":
            fallback_notes.append("LLM/视觉均未启用，使用本地名称/标签匹配")

        self.last_debug_info = {
            "llm_status": llm_status,
            "vision_status": vision_status,
            "tags": list(llm_tags),
            "keywords": list(dict.fromkeys([*llm_keywords, *local_keywords]))[:6],
            "candidate_count": len(candidates),
            "fallback": "；".join(dict.fromkeys([note for note in fallback_notes if note])),
            "reason": llm_reason,
        }
        return [ImageModel.from_db_row(self._dict_to_row(r)) for r in selected_rows]

    @staticmethod
    def _calc_candidate_count(top_k: int) -> int:
        """根据 top_k 计算候选池大小，并限制在最小/最大阈值内。"""
        base_count = max(
            top_k * RecommendController.CANDIDATE_MULTIPLIER,
            RecommendController.MIN_CANDIDATE_COUNT,
        )
        return min(base_count, RecommendController.MAX_CANDIDATE_COUNT)

    @staticmethod
    def _extract_keywords(context: str) -> list[str]:
        tokens = re.findall(r"[\u4e00-\u9fff]{1,8}|[a-zA-Z0-9_]{2,20}", context.lower())
        stopwords = {
            "我们",
            "你们",
            "他们",
            "这个",
            "那个",
            "一下",
            "就是",
            "然后",
            "可以",
            "怎么",
            "什么",
            "今天",
            "真的",
            "有点",
            "但是",
            "还是",
        }
        result: list[str] = []
        for token in tokens:
            t = token.strip()
            if not t or t in stopwords:
                continue
            candidates = [t]
            if re.fullmatch(r"[\u4e00-\u9fff]+", t) and len(t) > 2:
                for n in (2, 3, 4):
                    if len(t) < n:
                        continue
                    for idx in range(0, len(t) - n + 1):
                        candidates.append(t[idx : idx + n])
            for cand in candidates:
                if cand and cand not in stopwords and cand not in result:
                    result.append(cand)
        return result[:8]

    def _rank_candidates(
        self,
        context: str,
        all_images: list[dict],
        llm_tags: list[str],
        llm_keywords: list[str],
        llm_image_ids: list[int],
        local_keywords: list[str],
    ) -> list[dict]:
        llm_tag_set = {t.lower() for t in llm_tags}
        keyword_set = {k.lower() for k in llm_keywords if k}
        local_keyword_set = {k.lower() for k in local_keywords if k}
        id_boost_map = {img_id: max(1.0, 3.0 - idx * 0.5) for idx, img_id in enumerate(llm_image_ids)}
        scored: list[tuple[float, int, dict]] = []

        for idx, image in enumerate(all_images):
            tags = image.get("tags", []) or []
            name = (image.get("name") or "").lower()
            tags_l = [str(tag).lower() for tag in tags]
            tag_text = " ".join(tags_l)
            combined = " ".join([name, *tags_l])

            score = 0.0
            score += 2.5 * sum(1 for tag in tags_l if tag in llm_tag_set)
            score += 2.0 * sum(1 for kw in keyword_set if kw in tag_text)
            score += 1.6 * sum(1 for kw in local_keyword_set if kw in tag_text)
            score += 1.2 * sum(1 for kw in keyword_set if kw in name)
            score += 0.8 * sum(1 for kw in local_keyword_set if kw in name)
            score += id_boost_map.get(image.get("id"), 0.0)
            score += max(0.0, 0.3 - idx * 0.01)  # 小幅保留最近图片混入

            tie_seed = f"{context}|{image.get('id')}"
            tie_value = int(hashlib.md5(tie_seed.encode("utf-8")).hexdigest()[:8], 16)
            scored.append((score, tie_value, image))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored]

    @staticmethod
    def _build_candidate_scope(
        ranked_all: list[dict], preferred_ids: list[int], candidate_count: int
    ) -> tuple[list[dict], int]:
        """构建候选池并返回 (候选列表, LLM 种子命中数)。"""
        id_map = {img.get("id"): img for img in ranked_all}
        selected: list[dict] = []
        seen: set[int] = set()
        seeded = 0

        for image_id in preferred_ids:
            image = id_map.get(image_id)
            if image is None or image_id in seen:
                continue
            selected.append(image)
            seen.add(image_id)
            seeded += 1
            if len(selected) >= candidate_count:
                return selected, seeded

        for image in ranked_all:
            image_id = image.get("id")
            if image_id in seen:
                continue
            selected.append(image)
            if image_id is not None:
                seen.add(image_id)
            if len(selected) >= candidate_count:
                break
        return selected, seeded

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
