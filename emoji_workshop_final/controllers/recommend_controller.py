"""上下文推荐控制器

职责：
- 接收聊天上下文文字
- 用 jieba 分词提取关键词（过滤停用词）
- 按关键词匹配数据库标签，对图片打分排序
- 返回 Top-K 推荐结果

设计模式：策略模式 + 简单评分排序
"""

from __future__ import annotations

import jieba

from models.image_model import ImageModel
from services.database_service import DatabaseService


# 内置中文停用词集合（约 40 个高频无意义词）
_STOPWORDS: set[str] = {
    "的", "了", "是", "在", "我", "你", "他", "她", "它",
    "们", "这", "那", "有", "和", "与", "或", "也", "就",
    "都", "很", "不", "没", "为", "对", "从", "到", "把",
    "被", "让", "又", "再", "还", "才", "只", "可", "能",
    "会", "要", "想", "说", "去", "来", "吗", "啊", "呢",
    "哦", "嗯", "哈", "吧", "呀", "哎", "唉", "哇",
    "今天", "明天", "昨天", "什么", "怎么", "一个", "一下",
    "一些", "这个", "那个", "如果", "因为", "所以", "但是",
    "然后", "虽然", "不过", "而且", "已经", "现在", "自己",
    "知道", "觉得", "感觉", "真的", "其实", "一样", "时候",
    "一点", "可以", "应该", "需要", "没有", "这样", "那么",
}


class RecommendController:
    """上下文推荐控制器：根据聊天上下文推荐相关表情包"""

    def __init__(self, db_service: DatabaseService) -> None:
        self.db = db_service

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def extract_keywords(self, context: str) -> list[str]:
        """提取上下文关键词（供 UI 显示）

        Args:
            context: 输入的聊天上下文文字

        Returns:
            过滤停用词后的关键词列表
        """
        tokens = jieba.lcut(context)
        keywords = [
            t.strip()
            for t in tokens
            if len(t.strip()) >= 2 and t.strip() not in _STOPWORDS
        ]
        # 去重并保留顺序
        seen: set[str] = set()
        unique: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique

    def recommend(self, context: str, top_k: int = 3) -> list[ImageModel]:
        """根据上下文推荐表情包

        Args:
            context: 输入的聊天上下文文字
            top_k:   返回的最大推荐数量

        Returns:
            ImageModel 列表，按匹配度降序排列；
            若无任何匹配，返回最近使用的 Top-K 作为兜底。
        """
        keywords = self.extract_keywords(context)

        if keywords:
            rows = self.db.search_by_keywords(keywords, top_k)
            if rows:
                return [ImageModel.from_db_row(row) for row in rows]

        # 兜底：返回最近导入的 Top-K
        fallback_rows = self.db.get_all_images()[:top_k]
        return [ImageModel.from_db_row(row) for row in fallback_rows]
